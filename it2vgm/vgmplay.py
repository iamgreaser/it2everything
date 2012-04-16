#!/usr/bin/env python --
# -*- coding: utf-8 -*-
#
# VGM Player by Ben "GreaseMonkey" Russell, 2010.
# ...now eleventy-billion times faster!
# ...now with (experimental) SGC support!
#   ...which probably won't work with most stuff, but who cares!
#      it's in the works (at time of writing), and that's what matters!
#
# Whatever's not someone else's is public domain.
# If you want, you can redo the things yourself.
#
# Not intensively tested.
# hally's "MISSION76496" sounds butty, for instance
# ... actually it sounds fine now.
#
# Only does PSG.
#
# Anything "missing"? Look up the spec:
# - http://www.smspower.org/Music/VGMFileFormat
# - http://www.smspower.org/uploads/Music/vgmspec150.txt

import sys,struct,time
import gzip
from cStringIO import StringIO
import ossaudiodev
import array

# by Maxim (of SMS Power!, not DigitalMZX)
VOLTAB = [v>>(15-5) for v in [
	32767, 26028, 20675, 16422, 13045, 10362,  8231,  6568,
	5193,  4125,  3277,  2603,  2067,  1642,  1304,     0
]]

class SN76489:
	def __init__(self,clk,tap,shift):
		self.clk = clk
		self.clkinc = self.clk/22050
		self.tap = tap
		self.shift = shift
		self.shadd = 1<<(shift-1)
		self.vol = [0,0,0,0] # precalc'd vol
		self.frq = [0,0,0,0]
		self.soffs = [0,0,0,0]
		self.offs = [0,0,0,0]
		self.ch3p = 7
		self.latch = None
		self.precalc()
	
	def precalc(self):
		self.wfs = [-1,1]
		self.wfp = [0 for i in xrange(self.shift-1)] + [1]
		self.wfn = []
		
		# Doing a Galois LFSR instead.
		# We have to reverse the tapped bits.
		# I have confirmed this is identical to the Fibonacci LFSR,
		# at least for the SMS (SN76496).
		
		# reverse tapped bits to obtain Galois LFSR
		tap = 0
		tpr = self.tap
		for i in xrange(self.shift):
			tap = (tap<<1)|(tpr&1)
			tpr >>= 1
		
		self.wfn = []
		v = self.shadd
		while True:
			self.wfn.append((v&1)*2-1)
			v = (v>>1)^(tap if v&1 else 0)
			if v == self.shadd:
				break
		
		# Go ahead and check if you must.
		# This commented code below uses the algo that finaldave supplied
		# in that big doc by Maxim of smspower.org.
		
		#k = []
		#v = self.shadd
		#while True:
		#	k.append(v&1)
		#	
		#	p = v&self.tap
		#	p ^= p>>8
		#	p ^= p>>4
		#	p ^= p>>2
		#	v = (v>>1)|(self.shadd if (p^(p>>1))&1 else 0)
		#	if v == self.shadd:
		#		break
		#
		#assert len(k) == len(self.wfn)
		#for i in xrange(len(k)):
		#	#print k[i], self.wfn[i]
		#	assert k[i] == self.wfn[i]
		
		self.ls = len(self.wfs)
		self.lp = len(self.wfp)
		self.ln = len(self.wfn)
		print self.ln
		for i in xrange(self.clk/16):
			self.wfs.append(self.wfs[-self.ls])
			self.wfp.append(self.wfp[-self.lp])
			self.wfn.append(self.wfn[-self.ln])
	
	def flip(self, ch):
		if ch == 3:
			self.val[3] = self.ch3v & 1
			self.ch3v = (self.ch3v >> 1) | (
				self.shadd if (
					self.calcpar(self.ch3v&self.tap)
					if self.ch3p & 4
					else self.ch3v & 1
				) else 0
			)
		else:
			self.val[ch] = -1*self.val[ch]
	
	def feed(self, v):
		if v & 0x80:
			self.latch = ((v>>5)&3)|((v>>2)&4)
			ch = self.latch&3
			if self.latch & 4:
				self.vol[ch] = VOLTAB[v&15]
			elif ch == 3:
				if not ((v&4) and (v&4)==(self.ch3p&4)):
					self.offs[3] = 0
				self.ch3p = v&7
			else:
				self.frq[ch] = (self.frq[ch] & 0x3F0)|(v&15)
		elif self.latch != None:
			ch = self.latch&3
			if self.latch & 4:
				self.vol[ch] = VOLTAB[v&15]
			elif ch == 3:
				if not ((v&4) and (v&4)==(self.ch3p&4)):
					self.offs[3] = 0
				self.ch3p = v&7
			else:
				self.frq[ch] = (self.frq[ch] & 0x00F)|((v&63)<<4)
		
		if (self.ch3p&3) == 3:
			self.frq[3] = self.frq[2]*2
		else:
			self.frq[3] = 0x20<<(self.ch3p&3)
	
	def wsmp(self, buf, offs, c):
		#print [self.frq[i] for i in xrange(4)],[self.vol[i] for i in xrange(4)]
		ov = 0
		for ch in xrange(4):
			f = (self.frq[ch]*16)
			if not f:
				continue
			
			if ch == 3:
				if self.ch3p&4:
					wf = self.wfn
					wl = self.ln
				else:
					wf = self.wfp
					wl = self.lp
			else:
				wf = self.wfs
				wl = self.ls
			
			o = self.offs[ch]*f + self.soffs[ch]
			ci = self.clkinc
			v = self.vol[ch]
			for i in xrange(c):
				if self.frq[ch]:
					buf[offs+i] += wf[(o+i*ci)//f]*v
			
			self.offs[ch] = ((o+c*ci)//f)%wl
			self.soffs[ch] = (o+c*ci)%f

class SMSPager:
	def __init__(self):
		self.direct = [0 for i in xrange(0x400000)]
		self.ram = [0 for i in xrange(0x2000)]
		self.mapper = [0 for i in xrange(4)]
		self.sram = [0 for i in xrange(0x4000)]
		self.usesram = False
	
	def __setitem__(self, idx, val):
		if idx >= 0xC000:
			#print "WRITE %04X = %02X" % (idx, val)
			self.ram[idx&0x1FFF] = val
			if idx >= 0xFFFC:
				self.mapper[idx-0xFFFC] = val
				self.usesram = not not (self.mapper[0] & 8)
		elif self.usesram and idx >= 0x8000:
			self.sram[idx-0x8000] = val
	
	def __getitem__(self, idx):
		if idx >= 0xC000:
			return self.ram[idx&0x1FFF]
		elif self.usesram and idx >= 0x8000:
			return self.sram[idx-0x8000]
		elif idx >= 0x8000:
			return self.direct[idx-0x8000+(self.mapper[3]<<14)]
		elif idx >= 0x4000:
			return self.direct[idx-0x4000+(self.mapper[2]<<14)]
		elif idx >= 0x0400:
			return self.direct[idx+(self.mapper[1]<<14)]
		else:
			return self.direct[idx]

# For SGC player.
# Seriously, I'm going to at least attempt this.
# NOTE: this will stop running once it reaches a PC of 0x0000 except in ROM mode.
# TODO?: exact timing?
OPD_ALU = ["ADD A, ","ADC A, ","SUB ","SBC A, ","AND ","OR ","XOR ","CP "]
OPD_R8 = ["B","C","D","E","H","L","(HL)","A"]
OPD_R8X = ["B","C","D","E","IXH","IXL","(IX+dammit)","A"]
OPD_R8Y = ["B","C","D","E","IYH","IYL","(IY+dammit)","A"]
OPD_R16A = ["BC","DE","HL","SP"]
OPD_R16B = ["BC","DE","HL","AF"]
OPD_R16AX = ["BC","DE","IX","SP"]
OPD_R16BX = ["BC","DE","IX","AF"]
OPD_R16AY = ["BC","DE","IY","SP"]
OPD_R16BY = ["BC","DE","IY","AF"]
OPD_CC = ["NZ","Z","NC","C","PO","PE","P","M"]
OPD_ROT = ["RLC","RRC","RL","RR","SLA","SRA","SLL","SRL"]
class Z80:
	def __init__(self, load, sp, mem, rst, acc, sn, mapper, isrom=False):
		self.sn = sn
		
		# normal registers
		# flags = 6
		self.r8 = [0 for i in xrange(8)]
		self.r8[7] = acc
		self.ix = 0
		self.iy = 0
		self.inter = True
		
		# shadow registers
		self.r8p = [0 for i in xrange(8)]
		
		# that one other register
		self.sp = sp
		
		# RST jump vectors
		self.rst = rst
		
		# FIXME: will not handle a banked ROM
		self.mem = SMSPager()
		
		for i in xrange(4):
			self.mem[0xFFFC+i] = mapper[i]
		for i in xrange(len(mem)):
			self.mem.direct[load+i] = ord(mem[i])
		
		self.isrom = isrom
	
	def push(self, v):
		self.sp -= 2
		assert self.sp >= 0xC000
		#print "PUSH: %04X = %04X" % (self.sp, v)
		self.mem[self.sp] = v&255
		self.mem[self.sp+1] = (v>>8)&255
	
	def pop(self):
		v = self.mem[self.sp] | (self.mem[self.sp+1]<<8)
		#print "POP: %04X = %04X" % (self.sp, v)
		self.sp += 2
		assert self.sp < 0x10000
		return v
	
	def readhl(self, dbank, delt=0):
		#if dbank:
		#	raise Exception("TODO IXY readhl")
		
		if dbank == 0xDD:
			hl = (self.ix+delt)&0xFFFF
		elif dbank:
			hl = (self.iy+delt)&0xFFFF
		else:
			hl = self.r8[5]|(self.r8[4]<<8)
		
		return self.mem[hl]
	
	def writehl(self, dbank, v, delt=0):
		if dbank == 0xDD:
			hl = (self.ix+delt)&0xFFFF
		elif dbank:
			hl = (self.iy+delt)&0xFFFF
		else:
			hl = self.r8[5]|(self.r8[4]<<8)
		
		self.mem[hl] = v
	
	# Ugh I have to do this @_@
	def sign8(self, v):
		return v-0x100 if v & 0x80 else v
	
	# This helped a LOT: http://www.z80.info/z80sflag.htm
	# It even indicates what bits 5 and 3 do. Nifty.
	def alu(self, y, va, vb):
		assert va == (va&255)
		assert vb == (vb&255)
		
		if y == 0 or y == 1: # ADD/ADC
			y &= self.r8[6]
			nv = va+vb+y
			nv2 = self.sign8(va)+self.sign8(vb)+y
			
			self.r8[6] = (nv&0xA8)|((va&15)+(vb&15)+y) & 0x10
			
			if nv != (nv&255):
				self.r8[6] |= 0x01
			if nv2 < -128 or nv2 > 127:
				self.r8[6] |= 0x02
			if not (nv&255):
				self.r8[6] |= 0x40
			
			return nv&255
		elif y == 2 or y == 3 or y == 7: # SUB/SBC/CP
			cp = y == 7
			y &= self.r8[6]
			if cp:
				y = 0
			nv = va-vb-y
			nv2 = self.sign8(va)-self.sign8(vb)-y
			
			if cp:
				self.r8[6] = (va&0x28)|(nv&0x80)|((va&15)-(vb&15)-y) & 0x10
			else:
				self.r8[6] = (nv&0xA8)|((va&15)-(vb&15)-y) & 0x10
			
			if nv != (nv&255):
				self.r8[6] |= 0x01
			if nv2 < -128 or nv2 > 127:
				self.r8[6] |= 0x02
			if not (nv&255):
				self.r8[6] |= 0x40
			
			if cp:
				return va
			else:
				return nv&255
		else:
			nv = 0
			if y == 4:
				nv = va&vb
			elif y == 5:
				nv = va^vb
			else:
				nv = va|vb
			
			self.r8[6] = (nv&0xA8)|(0x10 if y == 4 else 0)
			
			# calc parity
			self.calcparity(nv)
			
			if not nv:
				self.r8[6] |= 0x40
			
			return nv
	
	def calcparity(self, v):
		p = v^(v>>4)
		p ^= p>>2
		self.r8[6] |= (((p^(p>>1)^1)&1)<<2)
	
	# yes, SLA is perfectly legal in my book
	def rot(self, y, v):
		assert v == (v&255)
		
		# flags are SZ503P0C
		nv = c = 0
		
		# memo to self: C stands for Circular, *NOT* Carry!
		if y == 0: # RLC r
			nv = (v << 1) | (v>>7)
			c = nv >> 8
		elif y == 1: # RRC r
			nv = (v >> 1) | ((v&1)<<7)
			c = v & 1
		elif y == 2: # RL r
			nv = (v << 1) | (self.r8[6]&1)
			c = nv >> 8
		elif y == 3: # RR r
			nv = (v >> 1) | (self.r8[6]&1)
			c = v & 1
		elif y == 4: # SLA r
			print "%04X: SLA?" % self.pc
			nv = (v << 1) | 1
			c = nv >> 8
		elif y == 5: # SRA r
			nv = (v >> 1) | (self.r8[6]&128)
			c = v & 1
		elif y == 6: # SLL r
			nv = v << 1
			c = nv >> 8
		elif y == 7: # SRL r
			nv = v >> 1
			c = v & 1
		
		self.r8[6] = (nv&0xA8)|c
		
		if not (nv&255):
			self.r8[6] |= 0x40
		
		# calc parity
		self.calcparity(nv)
		
		if not nv:
			self.r8[6] |= 0x40
		
		return nv & 255
		
	
	def portout(self, port, v):
		#print "port %02X = %02X" % (port, v)
		if port == 0x06: # Game Gear stereo
			pass
		elif (port&0xFC) == 0x90: # YM2413
			# not emulated here
			pass
		elif port == 0xFD:
			sys.stdout.write(chr(v))
			sys.stdout.flush()
		else:
			p = port&0xC1
			if p == 0x41:
				self.sn.feed(v)#^15)
	
	def fetch(self):
		v = self.mem[self.pc]
		self.pc += 1 # have to run it fast!
		return v
	
	def call(self, pc):
		self.push(0x0000)
		self.pc = pc
		self.run()
	
	# For debugging.
	def opdecode(self, opc, pc, dbank=None):
		x = opc>>6
		y = (opc>>3)&7
		z = opc&7
		
		if x == 0:
			if z == 0:
				if y == 0:
					return "NOP"
				elif y == 1:
					return "EX AF, AF'"
				else:
					return "%s $%04X" % (
						["DJNZ","JR","JR NZ,","JR Z,","JR NC,","JR C,"][y-2]
						,((self.sign8(self.mem[pc])+pc+1)&0xFFFF)
					)
			elif z == 1:
				if y&1:
					if dbank:
						if dbank == 0xDD:
							return "ADD IX, %s" % OPD_R16AX[y>>1]
						else:
							return "ADD IY, %s" % OPD_R16AY[y>>1]
					else:
						return "ADD HL, %s" % OPD_R16A[y>>1]
				else:
					l = self.mem[pc]
					h = self.mem[pc+1]
					return "LD %s, $%04X" % (OPD_R16A[y>>1], (h<<8)|l)
			elif z == 2:
				if y & 4:
					l = self.mem[pc]
					h = self.mem[pc+1]
					return ["LD ($%04X), HL","LD HL, ($%04X)","LD ($%04X), A","LD A, ($%04X)"][y-4] % ((h<<8)|l)
				else:
					return ["LD (BC), A","LD A, (BC)","LD (DE), A","LD A, (DE)"][y]
			elif z == 3:
				if dbank:
					if dbank == 0xDD:
						return "%s %s" % (["INC","DEC"][y&1], OPD_R16AX[y>>1])
					else:
						return "%s %s" % (["INC","DEC"][y&1], OPD_R16AY[y>>1])
				else:
					return "%s %s" % (["INC","DEC"][y&1], OPD_R16A[y>>1])
			elif (z&6) == 4:
				if dbank:
					if dbank == 0xDD:
						if y == 6:
							return "%s (IX%+d)" % (["INC","DEC"][z&1], self.mem[pc])
						else:
							return "%s %s" % (["INC","DEC"][z&1], OPD_R8X[y])
					else:
						if y == 6:
							return "%s (IY%+d)" % (["INC","DEC"][z&1], self.mem[pc])
						else:
							return "%s %s" % (["INC","DEC"][z&1], OPD_R8Y[y])
				else:
					return "%s %s" % (["INC","DEC"][z&1], OPD_R8[y])
			elif z == 6:
				if dbank:
					if dbank == 0xDD:
						if y == 6:
							return "LD (IX%+d), $%02X" % (self.sign8(self.mem[pc])-2, self.mem[pc+1])
						else:
							return "LD %s, $%02X" % (OPD_R8X[y], self.mem[pc])
					else:
						if y == 6:
							return "LD (IY%+d), $%02X" % (self.sign8(self.mem[pc])-2, self.mem[pc+1])
						else:
							return "LD %s, $%02X" % (OPD_R8Y[y], self.mem[pc])
				else:
					return "LD %s, $%02X" % (OPD_R8[y], self.mem[pc])
			else: # z == 7
				return ["RLCA","RRCA","RLA","RRA","DAA","CPL","SCF","CCF"][y]
		elif x == 1:
			if opc == 0x76:
				return "HALT"
			else:
				return "LD %s, %s" % (OPD_R8[y], OPD_R8[z])
		elif x == 2:
			return "%s%s" % (OPD_ALU[y], OPD_R8[z])
		else: # x == 3
			if z == 0:
				return "RET %s" % OPD_CC[y]
			elif z == 1:
				if y & 1:
					return ["RET","EXX","JP HL","LD SP,HL"][y>>1]
				else:
					return "POP %s" % OPD_R16B[y>>1]
			elif z == 2:
				l = self.mem[pc]
				h = self.mem[pc+1]
				return "JP %s, $%04X" % (OPD_CC[y], (h<<8)|l)
			elif z == 3:
				if y == 0:
					l = self.mem[pc]
					h = self.mem[pc+1]
					return "JP $%04X" % ((h<<8)|l)
				elif y == 1:
					# CB PREFIX
					opc = self.mem[pc]
					pc += 1
					x = opc>>6
					y = (opc>>3)&7
					z = opc&7
					if x == 0:
						return "%s %s" % (OPD_ROT[y], OPD_R8[z])
					elif x == 1:
						return "BIT %d, %s" % (y, OPD_R8[z])
					elif x == 2:
						return "RES %d, %s" % (y, OPD_R8[z])
					else: # x == 3
						return "SET %d, %s" % (y, OPD_R8[z])
				elif y == 2:
					return "OUT ($%02X), A" % self.mem[pc]
				elif y == 3:
					return "IN A, ($%02X)" % self.mem[pc]
				else:
					return ["EX (SP), HL", "EX DE, HL", "DI", "EI"][y-4]
			elif z == 4:
				l = self.mem[pc]
				h = self.mem[pc+1]
				return "CALL %s, $%04X" % (OPD_CC[y], (h<<8)|l)
			elif z == 5:
				if y == 1:
					l = self.mem[pc]
					h = self.mem[pc+1]
					return "CALL $%04X" % ((h<<8)|l)
				elif y == 3:
					return "IX: " + self.opdecode(self.mem[pc], pc+1, 0xDD)
				elif y == 5:
					# ED PREFIX
					opc = self.mem[pc]
					pc += 1
					x = opc>>6
					y = (opc>>3)&7
					z = opc&7
					if x == 1:
						if z == 0:
							if y == 6:
								return "IN F, (C)"
							else:
								return "IN %s, (C)" % OPD_R8[y]
						elif z == 1:
							if y == 6:
								return "OUT (C), 0"
							else:
								return "OUT (C), %s" % OPD_R8[y]
						elif z == 2:
							if y & 1: # yes, it's backwards, i know, it's supposed to be
								return "ADC HL, %s" % OPD_R16A[y>>1]
							else:
								return "SBC HL, %s" % OPD_R16A[y>>1]
						elif z == 3:
							l = self.mem[pc]
							h = self.mem[pc+1]
							if y & 1:
								return "LD %s, ($%04X)" % (OPD_R16A[y>>1], ((h<<8)|l))
							else:
								return "LD ($%04X), %s" % (((h<<8)|l), OPD_R16A[y>>1])
						elif z == 4:
							return "NEG"
						elif z == 5:
							if y == 1:
								return "RETI"
							else:
								return "RETN"
						elif z == 6:
							return "IM %s" % ["0","0/1","1","2"][y&3]
						else: # z == 7
							return [
								"LD I, A",
								"LD R, A",
								"LD A, I",
								"LD A, R",
								"RRD",
								"RLD",
								"NOP",
								"NOP"
							][y]
					elif x == 2 and z <= 3 and y >= 4:
						return [
							["LDI","CPI","INI","OUTI"],
							["LDD","CPD","IND","OUTD"],
							["LDIR","CPIR","INIR","OTIR"],
							["LDDR","CPDR","INDR","OTDR"]
						][y-4][z]
					else:
						return "DOES NOT EXIST"
						
					
				elif y == 7:
					return "IY: " + self.opdecode(self.mem[pc], pc+1, 0xFD)
				else:
					return "PUSH %s" % OPD_R16B[y>>1]
			elif z == 6:
				return "%s$%02X" % (OPD_ALU[y], self.mem[pc])
			else: # z == 7
				return "RST $%02X" % (y<<3)
				
		
		return "???"
	
	def run(self):
		n = True
		t = 0
		oprep = False
		while self.isrom or self.pc:
			# some useful asserts
			for r in self.r8:
				assert r == (r&255)
			assert (self.ix&0xFFFF) == self.ix
			assert (self.iy&0xFFFF) == self.iy
			assert (self.pc&0xFFFF) == self.pc
			assert (self.sp&0xFFFF) == self.sp
			
			if n:
				dbank = 0
			else:
				n = True
			
			opc = self.fetch()
			if t != 0 and not oprep:
				print "%04X[%02X:%02X]: %02X: %s" % (self.pc-1, self.r8[6], self.r8[0], opc, self.opdecode(opc,self.pc))
				time.sleep(0.01)
				t -= 1
			
			oprep = False
			
			#time.sleep(0.1)
			x = opc & 0xC0
			z = opc & 0x07
			y = opc & 0x38
			#print x,y,z
			# TODO: sort these by opcode frequency
			# XXX: could possibly even do a JIT job (using exec/eval)?
			if x == 0x00:
				if z == 0:
					if y == 0x00: # NOP
						pass
						#print "NOP"
						#t = 10
						#time.sleep(1.0)
					elif y == 0x08: # EX af, af'
						self.r8[6], self.r8p[6] = self.r8p[6], self.r8p[6]
						self.r8[7], self.r8p[7] = self.r8p[7], self.r8p[7]
					elif y == 0x10: # DJNZ dd
						#print "DJNZ %i" % self.r8[0]
						self.r8[0] = (self.r8[0]-1)&255
						d = self.fetch()
						if self.r8[0]:
							self.pc += self.sign8(d)
					elif y == 0x18: # JR dd
						#print "JR"
						d = self.fetch()
						self.pc += self.sign8(d)
					else: # JR cc,dd
						ck = False
						if y == 0x20:
							ck = not (self.r8[6]&64)
						elif y == 0x28:
							ck = (self.r8[6]&64)
						elif y == 0x30:
							ck = not (self.r8[6]&1)
						else:
							ck = (self.r8[6]&1)
						
						d = self.fetch()
						
						#print "JRcc"
						#print "%04X: %i" % (self.pc, d)
						#time.sleep(1.0)
						
						if ck:
							self.pc += self.sign8(d)
				elif z == 1:
					if y & 0x08: # ADD HL, rr
						y = (y>>3) & 6
						
						# save flags
						f = self.r8[6]
						
						if dbank and y == 4:
							raise Exception("TODO IXY ADD HL, HL")
						
						if dbank:
							b = 0
							if dbank == 0xDD:
								b = self.ix
							else:
								b = self.iy
							
							l = self.alu(0, b&255, self.r8[y+1])
							h = self.alu(1, b>>8, self.r8[y])
							
							if dbank == 0xDD:
								self.ix = l|(h<<8)
							else:
								self.iy = l|(h<<8)
						
						else:
							self.r8[5] = self.alu(0, self.r8[5], self.r8[y+1])
							self.r8[4] = self.alu(1, self.r8[4], self.r8[y])
						
						# now, mask back the flags this doesn't touch
						self.r8[6] = (self.r8[6] & 0x39) | (f & 0xC4)
					else: # LD rr, nnnn
						y >>= 3
						if dbank and y == 4:
							l = self.fetch()
							h = self.fetch()
							if dbank == 0xDD:
								self.ix = l|(h<<8)
							else:
								self.iy = l|(h<<8)
						elif y == 6:
							l = self.fetch()
							h = self.fetch()
							self.sp = l|(h<<8)
						else:
							self.r8[y+1] = self.fetch()
							self.r8[y] = self.fetch()
				elif z == 2:
					y >>= 3
					#print y
					if y & 4:
						if dbank:
							raise Exception("TODO IXY LD (nnnn)")
						
						l = self.fetch()
						h = self.fetch()
						hl = l|(h<<8)
						#print ": %04X (%02X%02X)" % (self.pc,h,l)
						if y == 4: # LD (nnnn), hl
							self.mem[hl] = self.r8[5]
							self.mem[(hl+1)&0xFFFF] = self.r8[4]
						elif y == 5: # LD hl, (nnnn)
							self.r8[5] = self.mem[hl]
							self.r8[4] = self.mem[(hl+1)&0xFFFF]
						elif y == 6: # LD (nnnn), a
							self.mem[hl] = self.r8[7]
						else: # LD a, (nnnn)
							self.r8[7] = self.mem[hl]
					elif y == 0: # LD (bc), a
						self.mem[self.r8[1]|(self.r8[0]<<8)] = self.r8[7]
					elif y == 1: # LD a, (bc)
						self.r8[7] = self.mem[self.r8[1]|(self.r8[0]<<8)]
					elif y == 2: # LD (de), a
						self.mem[self.r8[3]|(self.r8[2]<<8)] = self.r8[7]
					else: # LD a, (de)
						self.r8[7] = self.mem[self.r8[3]|(self.r8[2]<<8)]
				elif z == 3:
					y >>= 3
					if y & 1: # DEC rr
						y &= 6
						if dbank and y == 4:
							if dbank == 0xDD:
								self.ix = (self.ix-1)&0xFFFF
							else:
								self.iy = (self.iy-1)&0xFFFF
						else:
							self.r8[y+1] = (self.r8[y+1]-1)&255
							if self.r8[y+1] == 255:
								self.r8[y] = (self.r8[y]-1)&255
					else: # INC rr
						if dbank and y == 4:
							if dbank == 0xDD:
								self.ix = (self.ix+1)&0xFFFF
							else:
								self.iy = (self.iy+1)&0xFFFF
						else:
							self.r8[y+1] = (self.r8[y+1]+1)&255
							if self.r8[y+1] == 0:
								self.r8[y] = (self.r8[y]+1)&255
				elif z == 4: # INC r
					y >>= 3
					delt = 0
					if dbank and ((y&6) == 4):
						raise Exception("TODO IXY INC h/l")
					
					if y == 6:
						if dbank:
							delt = self.fetch()
						v = self.readhl(dbank, delt)
					else:
						v = self.r8[y]
					
					f = self.r8[6] # doesn't affect carry flag
					nv = self.alu(0, v, 1)
					
					self.r8[6] = (self.r8[6]&0xFE)|(f&0x01)
					if y == 6:
						self.writehl(dbank, v, delt)
					else:
						self.r8[y] = nv
				elif z == 5: # DEC r
					y >>= 3
					delt = 0
					if dbank and ((y&6) == 4):
						raise Exception("TODO IXY DEC h/l")
					
					if y == 6:
						if dbank:
							delt = self.fetch()
						v = self.readhl(dbank, delt)
					else:
						v = self.r8[y]
					
					f = self.r8[6] # doesn't affect carry flag
					nv = self.alu(2, v, 1)
					
					self.r8[6] = (self.r8[6]&0xFE)|(f&0x01)
					if y == 6:
						self.writehl(dbank, v, delt)
					else:
						self.r8[y] = nv
					
				elif z == 6: # LD r, nn
					self.r8[y>>3] = self.fetch()
				else:
					#print "ALUrotA"
					y >>= 3
					
					# TODO flags
					if y & 4:
						raise Exception("todo %02X" % opc)
					else:
						self.r8[7] = self.rot(y, self.r8[7])
					
			elif x == 0x40:
				#print "LDr/r"
				y >>= 3
				
				iv = 0
				if z == 6:
					if y == 6:
						raise Exception("SYSTEM HALTED")
					elif dbank and y == 4:
						if dbank == 0xDD:
							iv = self.ix>>8
						else:
							iv = self.iy>>8
					elif dbank and y == 5:
						if dbank == 0xDD:
							iv = self.ix&255
						else:
							iv = self.iy&255
					else:
						delt = 0
						if dbank:
							delt = self.fetch()
						
						iv = self.readhl(dbank, delt)
				else:
					iv = self.r8[z]
				
				if y == 6:
					delt = 0
					if dbank:
						delt = self.fetch()
					
					self.writehl(dbank, iv, delt)
				elif dbank and y == 4:
					if dbank == 0xDD:
						self.ix = (self.ix&255)|(iv<<8)
					else:
						self.iy = (self.ix&255)|(iv<<8)
				elif dbank and y == 5:
					if dbank == 0xDD:
						self.ix = (self.ix&0xFF00)|iv
					else:
						self.iy = (self.ix&0xFF00)|iv
				else:
					self.r8[y] = iv
			elif x == 0x80:
				#print "ALUr"
				y >>= 3
				
				if z == 6:
					delt = 0
					if dbank:
						delt = self.fetch()
					
					self.r8[7] = self.alu(y, self.r8[7], self.readhl(dbank, delt))
				else:
					if dbank and (z&6) == 4:
						if z == 4:
							if dbank == 0xDD:
								self.r8[7] = self.alu(y, self.r8[7], self.ix>>8)
							else:
								self.r8[7] = self.alu(y, self.r8[7], self.iy>>8)
						else:
							if dbank == 0xDD:
								self.r8[7] = self.alu(y, self.r8[7], self.ix&255)
							else:
								self.r8[7] = self.alu(y, self.r8[7], self.iy&255)
					else:
						self.r8[7] = self.alu(y, self.r8[7], self.r8[z])
			else:
				if z == 0: # RET cc
					#print "RETcc"
					ck = False
					if y == 0: # nz
						ck = not (self.r8[6]&64)
					elif y == 8: # z
						ck = (self.r8[6]&64)
					elif y == 16: # nc
						ck = not (self.r8[6]&1)
					elif y == 24: # c
						ck = (self.r8[6]&1)
					elif y == 32: # po
						ck = not (self.r8[6]&4)
					elif y == 40: # pe
						ck = (self.r8[6]&4)
					elif y == 48:
						ck = not (self.r8[6]&128)
					elif y == 56:
						ck = (self.r8[6]&128)
					
					if ck:
						#s = "%04X:" % (self.sp)
						#for i in xrange(16):
						#	s += " %02X" % (self.mem[self.sp+i])
						#print s
						self.pc = self.pop()
				elif z == 1:
					y >>= 3
					if y & 1:
						if y == 1: # RET
							self.pc = self.pop()
						elif y == 3: # EXX
							#print "EXX"
							for i in xrange(6):
								self.r8[i], self.r8p[i] = self.r8p[i], self.r8[i]
						elif y == 5: # JP hl
							#print "JP hl"
							if dbank:
								raise Exception("TODO IXY JP hl")
							
							#print "%04X" % self.pc
							self.pc = self.r8[5]|(self.r8[4]<<8)
							#print "%04X" % self.pc
							#t = 20
						else: # LD sp, hl
							assert y == 7
							if dbank:
								raise Exception("TODO IXY LD sp, hl")
							
							self.sp = self.r8[5]|(self.r8[4]<<8)
					else: # POP rr
						hl = self.pop()
						if dbank and y == 4:
							if dbank == 0xDD:
								self.ix = hl
							else:
								self.iy = hl
						else:
							self.r8[y+1] = hl & 255
							self.r8[y] = hl >> 8
				elif z == 2:
					ck = False
					if y == 0: # nz
						ck = not (self.r8[6]&64)
					elif y == 8: # z
						ck = (self.r8[6]&64)
					elif y == 16: # nc
						ck = not (self.r8[6]&1)
					elif y == 24: # c
						ck = (self.r8[6]&1)
					elif y == 32: # po
						ck = not (self.r8[6]&4)
					elif y == 40: # pe
						ck = (self.r8[6]&4)
					elif y == 48:
						ck = not (self.r8[6]&128)
					elif y == 56:
						ck = (self.r8[6]&128)
					
					#print ck, self.r8[7]
					
					l = self.fetch()
					h = self.fetch()
					if ck:
						self.pc = l|(h<<8)
				elif z == 3:
					if y == 0: # JP nnnn
						l = self.fetch()
						h = self.fetch()
						self.pc = l|(h<<8)
					elif y == 8: # CB prefix
						# *OI!* DON'T EVEN *THINK* ABOUT DOING THE DDCB/FDCB TRICK!
						# (although i guess i'll *have* to support it @_@)
						delt = 0
						if dbank:
							delt = self.fetch()
						
						opc = self.fetch()
						x = opc & 0xC0
						z = opc & 0x07
						y = opc & 0x38
						
						if dbank and z != 6:
							print "ALERT! {DD/FD}CB TRICK!"
							print x,y>>3,z
						#	time.sleep(1.0)
							
						#print "%04X: CB%02X" % (self.pc-1, opc)
						# TODO confirm flags
						
						y >>= 3
						
						if x == 0x00: # rotate/shift r
							if z == 6:
								self.writehl(dbank, self.rot(y, self.readhl(dbank, delt)), delt)
							else:
								v = self.r8[z]
								if dbank:
									v = self.rot(y, self.readhl(dbank, delt))
									self.writehl(dbank, v, delt)
								else:
									v = self.rot(y, v)
								
								self.r8[z] = v
						elif x == 0x40: # BIT n, r
							if z == 6 or dbank:
								self.alu(4, self.readhl(dbank, delt), 1<<y)
							else:
								self.alu(4, self.r8[z],1<<y)
						elif x == 0x80: # RES n, r
							if z == 6:
								self.writehl(dbank, self.readhl(dbank, delt) & ~(1<<y), delt)
							else:
								v = self.r8[z]
								if dbank:
									v = self.readhl(dbank, delt) & ~(1<<y)
									self.writehl(dbank, v, delt)
								else:
									v &= ~(1<<y)
								
								self.r8[z] = v
						else: # SET n, r
							if z == 6:
								self.writehl(dbank, self.readhl(dbank, delt) | (1<<y), delt)
							else:
								v = self.r8[z]
								if dbank:
									v = self.readhl(dbank, delt) | (1<<y)
									self.writehl(dbank, v, delt)
								else:
									v &= ~(1<<y)
								
								self.r8[z] = v
					elif y == 16: # OUT (n), a
						self.portout(self.fetch(), self.r8[7])
					# 24: TODO? IN a, (n)
					# 32: TODO EX (sp), hl
					elif y == 32:
						if dbank == 0xDD:
							hl = self.ix
							self.ix = self.pop()
						elif dbank:
							hl = self.iy
							self.iy = self.pop()
						else:
							hl = self.r8[5]|(self.r8[4]<<8)
							sd = self.pop()
							self.r8[5] = sd&255
							self.r8[4] = sd>>8
						
						self.push(hl)
					elif y == 40: # EX de, hl
						# *NOT AFFECTED BY DD/FD*
						self.r8[4], self.r8[2] = self.r8[2], self.r8[4]
						self.r8[5], self.r8[3] = self.r8[3], self.r8[5]
					elif y == 48: # DI
						self.inter = False
					elif y == 56: # EI
						self.inter = True
					else:
						print y
						raise Exception("todo %02X" % opc)
				elif z == 4: # CALL f,nnnn
					ck = False
					if y == 0: # nz
						ck = not (self.r8[6]&64)
					elif y == 8: # z
						ck = (self.r8[6]&64)
					elif y == 16: # nc
						ck = not (self.r8[6]&1)
					elif y == 24: # c
						ck = (self.r8[6]&1)
					elif y == 32: # po
						ck = not (self.r8[6]&4)
					elif y == 40: # pe
						ck = (self.r8[6]&4)
					elif y == 48:
						ck = not (self.r8[6]&128)
					elif y == 56:
						ck = (self.r8[6]&128)
					
					l = self.fetch()
					h = self.fetch()
					if ck:
						self.push(self.pc)
						self.pc = l|(h<<8)
				elif z == 5:
					if y & 8:
						if y & 16: # ... do another round!
							# XXX: not quite done yet
							#raise Exception("todo prefix %02X" % opc)
							dbank = y
							n = False
						elif y == 0x28: # ED prefix
							opc = self.fetch()
							#print "%04X: ED%02X" % (self.pc-1, opc)
							x = opc & 0xC0
							z = opc & 0x07
							y = opc & 0x38
							if x == 0x40:
								if z == 3:
									l = self.fetch()
									h = self.fetch()
									hl = l|(h<<8)
									if y == 0x00:
										self.mem[hl] = self.r8[1]
										self.mem[hl+1] = self.r8[0]
									elif y == 0x08:
										self.r8[1] = self.mem[hl]
										self.r8[0] = self.mem[hl+1]
									elif y == 0x10:
										self.mem[hl] = self.r8[3]
										self.mem[hl+1] = self.r8[2]
									elif y == 0x18:
										self.r8[3] = self.mem[hl]
										self.r8[2] = self.mem[hl+1]
									elif y == 0x20:
										self.mem[hl] = self.r8[5]
										self.mem[hl+1] = self.r8[4]
									elif y == 0x28:
										self.r8[5] = self.mem[hl]
										self.r8[4] = self.mem[hl+1]
									elif y == 0x30:
										self.mem[hl] = self.sp&255
										self.mem[hl+1] = (self.sp>>8)&255
									elif y == 0x38:
										self.sp = self.mem[hl]|(self.mem[hl+1]<<8)
									else:
										raise Exception("todo ED %02X" % opc)
								elif z == 5:
									# not going to bother distinguishing RETI from RETN
									self.pc = self.pop()
								elif z == 6:
									self.im = ((y>>3)&2)-1
								else:
									print hex(y),z
									raise Exception("todo ED %02X" % opc)
							elif x == 0x80 and z <= 3 and y >= 0x20: # block opers
								y >>= 3
								# 	z=0	z=1	z=2	z=3
								# y=4	LDI	CPI	INI	OUTI
								# y=5	LDD	CPD	IND	OUTD
								# y=6	LDIR	CPIR	INIR	OTIR
								# y=7	LDDR	CPDR	INDR	OTDR
								
								#print z,y
								if z == 0: # LDI/D[R]
									v = self.readhl(None)
									
									q = self.r8[7]+v # for 3/5
									
									self.r8[6] = (
										(self.r8[6]&0xC1)
										|(4 if self.r8[0] or self.r8[1] else 0)
										|(q&0x08)
										|((q<<4)&0x20)
									)
									
									self.mem[self.r8[3]|(self.r8[2]<<8)] = v
								elif z == 1: # CPI/D[R]
									raise Exception("todo ED %02X" % opc)
								elif z == 2: # INI/D[R]
									# flags mostly affected as in DEC b
									# PV is absolutely incoherent
									raise Exception("todo ED %02X" % opc)
								elif z == 3: # OUTI/D | OTI/DR
									# flags mostly affected as in DEC b
									# PV is absolutely incoherent
									v = self.readhl(dbank)
									
									self.r8[6] = (
										(self.r8[6]&0x17)
										|((self.r8[0]-1)&0xA8)
									)
									if self.r8[0] == 1:
										self.r8[6] |= 64
									
									self.portout(self.r8[1], v)
								
								if y & 1:
									self.r8[6] |= 2
								
								if z & 2:
									if y & 1: # dec
										self.r8[5] = (self.r8[5]-1)&255
									else: # inc
										self.r8[5] = (self.r8[5]+1)&255
									
									self.r8[0] = (self.r8[0]-1)&255
								
								else:
									if y & 1: # dec
										self.r8[5] = (self.r8[5]-1)&255
										if self.r8[5] == 255:
											self.r8[4] = (self.r8[4]-1)&255
										
										self.r8[3] = (self.r8[3]-1)&255
										if self.r8[3] == 255:
											self.r8[2] = (self.r8[2]-1)&255
									else: # inc
										self.r8[5] = (self.r8[5]+1)&255
										if self.r8[5] == 0:
											self.r8[4] = (self.r8[4]+1)&255
										
										self.r8[3] = (self.r8[3]+1)&255
										if self.r8[3] == 0:
											self.r8[2] = (self.r8[2]+1)&255
									
									self.r8[1] = (self.r8[1]-1)&255
									if self.r8[1] == 255:
										self.r8[0] = (self.r8[0]-1)&255
								
								if y & 2: # repeat type
									if self.r8[0] or ((not (z & 2)) and self.r8[1]):
										self.pc -= 2
										oprep = True
						else: # CALL
							l = self.fetch()
							h = self.fetch()
							self.push(self.pc)
							self.pc = l|(h<<8)
					else: # PUSH rr
						y >>= 3
						if dbank and y == 4:
							if dbank == 0xDD:
								self.push(self.ix)
							else:
								self.push(self.iy)
						else:
							self.push(self.r8[y+1]|(self.r8[y]<<8))
				elif z == 6:
					self.r8[7] = self.alu(y>>3, self.r8[7], self.fetch())
				elif z == 7:
					self.push(self.pc)
					#self.pc = y # only on a real emulation!
					self.pc = self.rst[y>>3]
				else:
					raise Exception("todo %02X" % opc)

class SGC:
	def __init__(self, fname, isrom=False):
		fp = open(fname,"rb")
		if isrom:
			self.palntsc = 1
			self.refresh = 22050/50
			self.mapper = [0,0,1,2]
			self.ad_load = 0
			self.ad_init = 0
			self.ad_stack = 0xDFF0
			self.ad_rst = [0,8,16,24,32,40,48,56]
			self.ad_play = 0x38
			self.sng_start = 0
		else:
			magic = fp.read(4)
			if magic != "SGC\x1A":
				raise Exception("not an SGC file")
			ver = ord(fp.read(1))
			if ver != 0x01:
				raise Exception("not an SGC v1 file")
			
			self.palntsc = ord(fp.read(1))
			self.refresh = 0
			if self.palntsc == 0:
				self.refresh = 22050/60
			elif self.palntsc == 1:
				self.refresh = 22050/50
			else:
				raise Exception("unknown PAL/NTSC mode for file: %02X" % self.palntsc)
			
			fp.read(1) # reserved (defined as scanlines per interrupt or something)
			fp.read(1) # reserved
			
			self.ad_load, self.ad_init, self.ad_play, self.ad_stack = struct.unpack("<HHHH", fp.read(8))
			
			fp.read(2) # reserved
			self.ad_rst = [0]+[struct.unpack("<H", fp.read(2))[0] for i in xrange(7)]
			self.mapper = [ord(fp.read(1)) for i in xrange(4)]
			self.sng_start = ord(fp.read(1))
			self.sng_count = ord(fp.read(1))
			self.sfx_start = ord(fp.read(1))
			self.sfx_end = ord(fp.read(1))
			self.systype = ord(fp.read(1))
			
			if self.systype == 0x00:
				print "systype: Sega Master System"
			elif self.systype == 0x01:
				print "systype: Sega Game Gear"
			elif self.systype == 0x02:
				print "systype: Colecovision"
				raise Exception("system not supported")
			else:
				raise Exception("system not supported: %02X" % self.systype)
			
			fp.read(0x3F-0x29+1) # reserved
			self.inf_name = self.trimstr(fp.read(32))
			self.inf_author = self.trimstr(fp.read(32))
			self.inf_copyright = self.trimstr(fp.read(32))
			print "[%s][%s][%s]" % (self.inf_name, self.inf_author, self.inf_copyright)
			
		self.sn = SN76489(3579545, 0x0009, 16) # Sega Master System defaults
		
		self.z80 = Z80(self.ad_load, self.ad_stack, fp.read(), self.ad_rst, self.sng_start, self.sn, self.mapper, isrom)
		print "initialising"
		self.z80.call(self.ad_init)
		print "OK, ready to roll"
	
	def trimstr(self, s):
		return s[:s.index("\x00")] if "\x00" in s else s
	
	def play(self):
		self.dsp = ossaudiodev.open("w")
		self.dsp.setfmt(ossaudiodev.AFMT_U8)
		self.dsp.channels(1)
		self.dsp.speed(22050)
		abuf = [128 for i in xrange(11025)]
		rst = True
		smp = False
		die = False
		l = 0
		offs = 0
		while True:
			if rst:
				# From http://www.python.org/doc/essays/list2str.html
				self.dsp.write(array.array('B', abuf).tostring())
				#self.dsp.write(''.join(chr(v) for v in abuf))
				for i in xrange(11025):
					abuf[i] = 128
				l -= 11025-offs
				offs = 0
				
				if l < 0:
					l = 0
				
				rst = False
				if die:
					break
			
			if smp:
				if l > 0:
					if l+offs >= 11025:
						self.sn.wsmp(abuf, offs, 11025-offs)
						l -= 11025-offs
						rst = True
					else:
						self.sn.wsmp(abuf, offs, l)
						offs += l
						l = 0
						smp = False
				else:
					smp = False
			else:
				self.z80.call(self.ad_play)
				l = self.refresh
				smp = True
				#l = 22050
				#smp = True
				#die = True

class VGM:
	def __init__(self, fname):
		fp = open(fname,"rb")
		magic = fp.read(4)
		if magic[:3] == "\x1F\x8B\x08": # GZipped VGM stream
			# use StringIO as we'll be seeking
			fp.close()
			fp = gzip.open(fname,"rb")
			sio = StringIO(fp.read())
			fp.close()
			fp = sio
			magic = fp.read(4)
		
		if magic != "Vgm ":
			raise Exception("not a VGM file")
		
		self.eof, self.ver, self.snclk, self.ymclk = struct.unpack("<IIII", fp.read(16))
		self.gd3, self.smps, self.lpoffs, self.lpsmps = struct.unpack("<IIII", fp.read(16))
		
		# VGM 1.01
		self.rate = struct.unpack("<I", fp.read(4))
		if self.ver < 0x101:
			self.rate = 0
		
		# VGM 1.10
		self.sntap, self.snshift, _ = struct.unpack("<HBB", fp.read(4))
		self.ymclk2, self.ymclk3 = struct.unpack("<II", fp.read(8))
		if self.ver < 0x110:
			self.sntap = 0x0009
			self.snshift = 16
			self.ymclk2 = self.ymclk3 = self.ymclk
		
		# VGM 1.50
		self.vgmoffs, = struct.unpack("<I", fp.read(4))
		if self.ver < 0x150:
			self.vgmoffs = 0x40
		else:
			self.vgmoffs += 0x40
		
		fp.seek(self.vgmoffs)
		self.data = fp.read(self.eof-self.vgmoffs)+"\x66"
		self.doffs = 0
		
		self.sn = SN76489(self.snclk, self.sntap, self.snshift)
		
		print self.snclk
		
		fp.close()
	
	def play(self):
		self.dsp = ossaudiodev.open("w")
		self.dsp.setfmt(ossaudiodev.AFMT_U8)
		self.dsp.channels(1)
		self.dsp.speed(22050)
		abuf = [128 for i in xrange(11025)]
		rst = True
		smp = False
		die = False
		l = 0
		offs = 0
		flop = 0
		while True:
			if rst:
				# From http://www.python.org/doc/essays/list2str.html
				self.dsp.write(array.array('B', abuf).tostring())
				#self.dsp.write(''.join(chr(v) for v in abuf))
				for i in xrange(11025):
					abuf[i] = 128
				l -= 11025-offs
				offs = 0
				
				if l < 0:
					l = 0
				
				rst = False
				if die:
					break
			
			if smp:
				if flop > 1:
					l += flop/2
					flop &= 1
				if l > 0:
					if l+offs >= 11025:
						self.sn.wsmp(abuf, offs, 11025-offs)
						l -= 11025-offs
						rst = True
					else:
						self.sn.wsmp(abuf, offs, l)
						offs += l
						l = 0
						smp = False
				else:
					smp = False
			else:
				v = ord(self.data[self.doffs])
				self.doffs += 1
				if v == 0x4F: # Game Gear stereo
					self.doffs += 1
				elif v == 0x50: # PSG
					nv = ord(self.data[self.doffs])
					self.doffs += 1
					self.sn.feed(nv)
				elif v == 0x61: # wait any
					vl = ord(self.data[self.doffs])
					self.doffs += 1
					vh = ord(self.data[self.doffs])
					self.doffs += 1
					flop = (vl | (vh<<8))
					#print "flop %i" % flop
					smp = True
				elif v == 0x62: # wait NTSC
					flop = 735
					smp = True
				elif v == 0x63: # wait PAL
					flop = 882
					smp = True
				elif v == 0x66: # end of stream
					flop = 22050
					smp = True
					die = True
				elif v == 0x67: # data block
					ck = ord(self.data[self.doffs])
					self.doffs += 1
					if ck != 0x66:
						raise Exception("invalid data block")
					t = ord(self.data[self.doffs])
					self.doffs += 1
					v = ord(self.data[self.doffs])
					v |= ord(self.data[self.doffs+1])<<8
					v |= ord(self.data[self.doffs+2])<<16
					v |= ord(self.data[self.doffs+3])<<24
					self.doffs += 4
					length = v
					self.doffs += length
				elif v >= 0x70 and v <= 0x7F: # wait n+1 samples
					flop = (v+1)
					smp = True
				else:
					print "TODO %02X" % v
					flop = 22050
					smp = True
					die = True

fp = open(sys.argv[1],"rb")
magic = fp.read(4)
fp.close()
# XXX: support gzipped SGC files? it's not standard, though
if magic[:3] == "\x1F\x8B\x08" or magic[:4] == "Vgm ":
	vgm = VGM(sys.argv[1])
	vgm.play()
elif magic[:4] == "SGC\x1A":
	sgc = SGC(sys.argv[1])
	sgc.play()
else:
	# attempt to load as ROM
	print "UNKNOWN FORMAT - ATTEMPTING TO LOAD AS ROM"
	sgc = SGC(sys.argv[1],True)
	sgc.play()
	# raise Exception("unsupported format")
