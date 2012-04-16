#!/usr/bin/env python --
# -*- coding: utf-8 -*-
#
# IT2VGM, for all you Sega Master System + Impulse Tracker fans
#   (all you dreaded Modplug fans are BANNED)
#
# by Ben "GreaseMonkey" Russell, 2010. public domain.
#
# notes:
# - Bxx ends the piece and restarts at that paricular row.
# - tempo has been implemented for ages.
#     this just had an incredibly out-of-date note here.
#     just try to stick with 125 or 150 if you want to keep it simple.
# - sample volumes are ignored because samples are ignored.
# - samples are hardwired to 1 == square, 2 == white, 3 == periodic.
# - a lot of other stuff isn't handled.
#

import sys, struct
import math

# table by Maxim (of SMS Power!, not DigitalMZX)
VOLTAB = [v>>(15-6) for v in [
	32767, 26028, 20675, 16422, 13045, 10362,  8231,  6568,
	5193,  4125,  3277,  2603,  2067,  1642,  1304,     0
]]

# from the S3M spec, good ol' Future Crew :D
PERTAB = [
	1712,1616,1524,1440,1356,1280,1208,1140,1076,1016,960,907
]

# TODO other tables + some weird class
VIBTAB = [
	[math.sin((i*math.pi)/128.0) for i in xrange(256)],
]

IVOLTAB = []
for i in xrange(64+1):
	ni = 0
	nv = -1
	for j in xrange(16):
		if abs(i-VOLTAB[j]) < abs(i-nv):
			nv = VOLTAB[j]
			ni = j
	
	IVOLTAB.append(ni)

def nulltrim(s):
	return s[:s.index("\x00")] if "\x00" in s else s

def nullpad(s, l):
	return s[:l] + "\x00"*(l-len(s))

class IT2VGM:
	def __init__(self, fname):
		fp = open(fname,"rb")
		if fp.read(4) != "IMPM":
			raise Exception("this isn't an .it module")
		
		self.name = nulltrim(fp.read(26))
		fp.read(2) # skip pat highlight
		self.ordnum, self.insnum, self.smpnum, self.patnum = struct.unpack("<HHHH", fp.read(8))
		
		print "module: \"%s\"" % self.name
		print "O/I/S/P: %i, %i, %i, %i" % (self.ordnum, self.insnum, self.smpnum, self.patnum)
		
		fp.read(4) # skip version, assume we're not doing v1.xx crap
		# by the way, we don't even support instruments
		# actually we don't handle any of that crap
		# (assume not-old effects and incompatible Gxx like a real man)
		# also special is ignored but we store it anyway
		self.flags, self.special = struct.unpack("<HH", fp.read(4))
		self.gvol, self.mv, self.tpr, self.bpm = (ord(c) for c in fp.read(4))
		fp.read(12) # skip sep / pwd / message crap / "reserved" (timestamp)
		fp.read(64) # skip panning crap
		self.chvol = [ord(c) for c in fp.read(64)]
		
		self.ordlist = [ord(c) for c in fp.read(self.ordnum)]
		self.ordlist += [0xFF]*(258-self.ordnum)
		self.insptrs = struct.unpack("<"+("I"*self.insnum), fp.read(4*self.insnum))
		self.smpptrs = struct.unpack("<"+("I"*self.smpnum), fp.read(4*self.smpnum))
		self.patptrs = struct.unpack("<"+("I"*self.patnum), fp.read(4*self.patnum))
		# nobody cares about instruments
		
		# actually we don't care about samples either
		
		# load pattern data
		# we'll load the whole damn thing actually
		self.patlist = [self.loadpat(fp, self.patptrs[i]) for i in xrange(self.patnum)]
		fp.close()
		
		self.play()
	
	def read_row(self):
		for ch in xrange(64):
			self.pcsave[ch][6] = False
		
		while True:
			ch = self.curpat[self.curpos]
			self.curpos += 1
			if ch == 0:
				break
			
			k = ch & 0x80
			ch = (ch&0x7F)-1
			self.pcsave[ch][6] = True
			if k:
				self.pcsave[ch][0] = self.curpat[self.curpos]
				self.curpos += 1
			
			m = self.pcsave[ch][0]
			if m & 0x01:
				self.pcsave[ch][1] = self.curpat[self.curpos]
				self.curpos += 1
			if m & 0x02:
				self.pcsave[ch][2] = self.curpat[self.curpos]
				self.curpos += 1
			if m & 0x04:
				self.pcsave[ch][3] = self.curpat[self.curpos]
				self.curpos += 1
			if m & 0x08:
				self.pcsave[ch][4] = self.curpat[self.curpos]
				self.curpos += 1
				self.pcsave[ch][5] = self.curpat[self.curpos]
				self.curpos += 1
	
	def set_row(self, row):
		self.curpos = 0
		self.currow = row
		self.pcsave = [[0x00,None,None,None,None,None,False] for i in xrange(64)]
		
		for i in xrange(row):
			self.read_row()
	
	def psg_vol(self, ch, vol):
		self.stream.append(0x50)
		self.stream.append(0x90 | (ch<<5) | (vol&15))
	
	def psg_per(self, ch, per):
		self.stream.append(0x50)
		
		if ch == 3:
			self.stream.append(0x80 | (ch<<5) | (per&7))
		else:
			self.stream.append(0x80 | (ch<<5) | (per&15))
			self.stream.append(0x50)
			self.stream.append((per>>4)&63)
	
	def doeff(self, ch, tick):
		if not self.pcsave[ch][6]:
			return
		if not (self.pcsave[ch][0] & 0x88):
			return
		
		eft = self.pcsave[ch][4]
		efp = self.pcsave[ch][5]
		el = efp&15
		eh = efp>>4
		if eft >= 1 and eft <= 26 and efp:
			if (el and eh) or not eft in [8,9,10]:
				self.effsave[ch][eft-1] = efp
			elif el:
				self.effsave[ch][eft-1] = (self.effsave[ch][eft-1]&0xF0)|el
			elif eh:
				self.effsave[ch][eft-1] = (self.effsave[ch][eft-1]&15)|(eh<<4)
		
		sfp = self.effsave[ch][eft-1]
		sl = sfp&15
		sh = sfp>>4
		
		if eft == 1:
			if efp:
				self.tpr = efp
		elif eft == 2:
			self.currow = 0x8000
			self.curord = efp-1
		elif eft == 3:
			self.currow = 0x8000
			self.breakrow = efp
		elif eft == 20:
			if tick:
				if sh == 1:
					self.bpm += sl
					if self.bpm > 255:
						self.bpm = 255
				elif sh == 0:
					self.bpm -= sl
					if self.bpm < 32:
						self.bpm = 32
			else:
				if efp >= 32:
					self.bpm = efp
		elif eft == 22:
			if efp <= 128:
				self.gvol = efp
		elif eft == 23:
			if (
				(sl == 0 or sh == 0)
				if tick else
				(sl == 15 or sh == 15)
			):
				# TODO look up order
				if sh == 0:
					self.gvol -= sl
				elif sl == 0:
					self.gvol += sh
				elif sh == 15:
					self.gvol -= sl
				elif sl == 15:
					self.gvol += sh
				
				if self.gvol < 0:
					self.gvol = 0
				if self.gvol > 128:
					self.gvol = 128
		
		if ch < 4:
			if eft == 4 or eft == 11 or eft == 12:
				# handle S3M/IT quirk
				if (
					(sl == 0 or sh == 0)
					if tick else
					(sl == 15 or sh == 15)
				):
					# TODO look up order
					if sh == 0:
						self.cvol[ch] -= sl
					elif sl == 0:
						self.cvol[ch] += sh
					elif sh == 15:
						self.cvol[ch] -= sl
					elif sl == 15:
						self.cvol[ch] += sh
					
					if self.cvol[ch] < 0:
						self.cvol[ch] = 0
					if self.cvol[ch] > 64:
						self.cvol[ch] = 64
			elif eft == 9:
				pass # TODO Ixy
			elif eft == 13:
				if efp <= 64:
					self.chvol[ch] = efp
			elif eft == 14:
				if (
					(sl == 0 or sh == 0)
					if tick else
					(sl == 15 or sh == 15)
				):
					# TODO look up order
					if sh == 0:
						self.chvol[ch] -= sl
					elif sl == 0:
						self.chvol[ch] += sh
					elif sh == 15:
						self.chvol[ch] -= sl
					elif sl == 15:
						self.chvol[ch] += sh
					
					if self.chvol[ch] < 0:
						self.chvol[ch] = 0
					if self.chvol[ch] > 64:
						self.chvol[ch] = 64
			# not doing Oxx!
			# not doing Pxx!
			elif eft == 17:
				pass # TODO Qx0 ? - not retriggering!
			elif eft == 18:
				pass # TODO Rxy
			elif eft == 19:
				if sh == 0xC:
					if tick and tick >= sl:
						self.playing[ch] = False
			# not doing Xxx!
			# not doing Yxy!
			# not doing Zxx!
			
		
		if ch < 3:
			if eft == 5:
				if efp:
					self.effsave[ch][7-1] = efp
				
				xfp = self.effsave[ch][7-1]
				xl = xfp&15
				xh = xfp>>4
				
				if xh == 0xE and not tick:
					self.cper[ch] += xl
				elif xh == 0xF and not tick:
					self.cper[ch] += xl*4
				elif xh <= 0xD and tick:
					self.cper[ch] += xfp*4
				self.fper[ch] = self.cper[ch]
			elif eft == 6:
				if efp:
					self.effsave[ch][7-1] = efp
				
				xfp = self.effsave[ch][7-1]
				xl = xfp&15
				xh = xfp>>4
				
				if xh == 0xE and not tick:
					self.cper[ch] -= xl
				elif xh == 0xF and not tick:
					self.cper[ch] -= xl*4
				elif xh <= 0xD and tick:
					self.cper[ch] -= xfp*4
				
				self.fper[ch] = self.cper[ch]
			elif eft == 7 or eft == 12:
				if tick:
					xfp = self.effsave[ch][7-1]
					
					# TODO look up a particular Storlek test
					if self.cper[ch] < self.tper[ch]:
						self.cper[ch] += xfp*4
						if self.cper[ch] >= self.tper[ch]:
							self.cper[ch] = self.tper[ch]
					elif self.cper[ch] > self.tper[ch]:
						self.cper[ch] -= xfp*4
						if self.cper[ch] <= self.tper[ch]:
							self.cper[ch] = self.tper[ch]
					
					self.fper[ch] = self.cper[ch]
			elif eft == 8 or eft == 11:
				xfp = self.effsave[ch][8-1]
				xl = xfp&15
				xh = xfp>>4
				
				# TODO find out if it's pre- or post-increment
				self.vibpos[ch] = (self.vibpos[ch] + xh*4)&255
				z = xl*4.0*VIBTAB[self.vibtype[ch]&3][self.vibpos[ch]]
				self.fper[ch] = int(self.cper[ch]+z+0.52)
			elif eft == 10:
				k = tick % 3
				# calc is very expensive!
				if k == 1 and sh:
					self.fper[ch] = int(self.cper[ch] * 2.0**(-float(sh)/12.0))
				elif k == 2 and sl:
					self.fper[ch] = int(self.cper[ch] * 2.0**(-float(sl)/12.0))
				
			elif eft == 21:
				# TODO test this
				if efp:
					self.effsave[ch][8-1] = xfp
				
				xfp = self.effsave[ch][8-1]
				xl = xfp&15
				xh = xfp>>4
				
				# TODO find out if it's pre- or post-increment
				self.vibpos[ch] = (self.vibpos[ch] + xh)&255
				z = xl*VIBTAB[self.vibtype[ch]&3][self.vibpos[ch]]
				self.fper[ch] = int(self.cper[ch]+z+0.52)
	
	def load_crap(self, ch):
		if not self.pcsave[ch][6]:
			return
		
		m = self.pcsave[ch][0]
		
		ins = 0
		vol = -1
		eft = 0
		efp = 0
		if m & 0x88:
			eft = self.pcsave[ch][4]
			efp = self.pcsave[ch][5]
			if eft == 19 and (efp>>4) == 0xD: # delay
				if not self.curtick:
					return
		
		if m & 0x11:
			note = self.pcsave[ch][1]
			if note < 120:
				self.playing[ch] = True
				
				if ch == 3:
					k = self.tper[ch]&4
					if note == 57:
						self.tper[ch] = k|2
					elif note == 69:
						self.tper[ch] = k|1
					elif note == 81:
						self.tper[ch] = k|0
					else:
						self.tper[ch] = k|3
				else:
					self.tper[ch] = (PERTAB[note%12]<<2)>>(note/12)
			elif note == 255:
				pass # note off does nothing w/o instruments
			elif note == 254:
				# note cut
				#self.cvol[ch] = 0
				self.playing[ch] = False
			else:
				# 253 is blank but we'll ignore it as some do 253 as note fade
				# for example older versions of schism
				pass # and note fade does nothing w/o instruments
		if m & 0x22:
			ins = self.pcsave[ch][2]
			self.cvol[ch] = 64
		if m & 0x44:
			vol = self.pcsave[ch][3]
		
		if ch == 3:
			if ins == 2:
				self.tper[ch] = (self.tper[ch] & 3) | 4
			elif ins == 3:
				self.tper[ch] = (self.tper[ch] & 3) | 0
		
		if (m & 0x11) and eft != 7 and eft != 12:
			#print "tf", ch, self.cper[ch], self.tper[ch]
			self.cper[ch] = self.tper[ch]
			if ch < 3 and self.vibtype[ch] & 4:
				self.vibpos[ch] = 0
		
		if vol >= 0 and vol <= 64:
			self.cvol[ch] = vol
	
	def save_row(self):
		self.rowsave[self.curord][self.currow] = (len(self.stream), self.streampos)

	def play(self):
		self.psgvols = [15,15,15,15]
		self.psgpers = [0,0,0,4]
		self.lpsgvols = [15,15,15,15]
		self.lpsgpers = [0,0,0,4]
		self.playing = [False, False, False, False]
		self.pcsave = [[0x00,None,None,None,None,None] for i in xrange(64)]
		self.effsave = [[0 for j in xrange(26)] for i in xrange(64)]
		self.rowsave = [[None]*256 for i in xrange(self.ordnum)]
		self.vibtype = [4 for i in xrange(3)]
		self.trmtype = [4 for i in xrange(3)]
		self.vibpos = [0 for i in xrange(3)]
		self.trmpos = [0 for i in xrange(3)]
		self.tmrctr = [0 for i in xrange(4)]
		self.cper = [1023,1023,1023,4]
		self.tper = [1023,1023,1023,4]
		self.fper = [1023,1023,1023,4]
		self.cvol = [0 for i in xrange(4)]
		
		self.curord = -1
		self.currow = -1
		self.breakrow = self.curpat = 0
		self.curpos = 0
		self.curtick = 0
		
		self.stream = []
		self.streampos = 0
		self.psg_vol(0,15)
		self.psg_vol(1,15)
		self.psg_vol(2,15)
		self.psg_vol(3,15)
		self.psg_per(0,1023)
		self.psg_per(1,1023)
		self.psg_per(2,1023)
		self.psg_per(3,4)
		
		self.vgmloop_ptr = len(self.stream)
		self.vgmloop_smp = 0
		
		while True:
			self.curord += 1
			while self.ordlist[self.curord] == 0xFE:
				self.curord += 1
			
			if self.ordlist[self.curord] == 0xFF:
				self.currow = self.breakrow = 0
				self.curord = 0
				self.vgmloop_ptr = -1
				break
			
			self.cprows, self.curpat = self.patlist[self.ordlist[self.curord]]
			self.currow = self.breakrow
			self.breakrow = 0
			if self.currow >= self.cprows:
				self.currow = 0
			
			self.set_row(self.currow)
			self.read_row()
			for i in xrange(4):
				self.load_crap(i)
			
			if self.rowsave[self.curord][self.currow]:
				break
			
			self.save_row()
			
			while True:
				for i in xrange(4):
					self.fper[i] = self.cper[i]
					if self.curtick and self.pcsave[i][4] == 19:
						efp = self.pcsave[i][5]
						if (efp>>4) == 0xD:
							if efp == 0xD0:
								efp += 1
							
							if (efp&15) == self.curtick:
								self.load_crap(i)
						
				for i in xrange(64):
					self.doeff(i, self.curtick)
				
				for i in xrange(4):
					self.psgvols[i] = IVOLTAB[(self.cvol[i]*self.gvol*self.chvol[i])/(128*64)] if self.playing[i] else 15
					self.psgpers[i] = ((self.fper[i]+2)>>2) if i != 3 else self.tper[i]
					if self.psgvols[i] != self.lpsgvols[i]:
						self.lpsgvols[i] = self.psgvols[i]
						self.psg_vol(i,self.psgvols[i])
						#print self.psgvols[i], self.playing[i]
					if self.psgpers[i] != self.lpsgpers[i]:
						self.lpsgpers[i] = self.psgpers[i]
						if self.psgpers[i] > 1023:
							print "PER EXCEED, clipped", i, self.psgpers[i]
							self.psgpers[i] = 1023
						if self.psgpers[i] < 1:
							print "PER EXCEED, clipped", i, self.psgpers[i]
							self.psgpers[i] = 1
						self.psg_per(i,self.psgpers[i])
						#print "per", self.psgpers[i]
						
				
				spi = 110250/self.bpm
				if spi != 0:
					self.writespeed(spi)
					self.streampos += spi
				
				self.curtick += 1
				if self.curtick >= self.tpr:
					self.curtick = 0
					self.currow += 1
					if self.currow >= self.cprows:
						break
					
					self.read_row()
					for i in xrange(4):
						self.load_crap(i)
					if self.rowsave[self.curord][self.currow] == None:
						self.save_row()
		
		if self.vgmloop_ptr != -1:
			vl = self.rowsave[self.curord][self.currow]
			if vl != None:
				self.vgmloop_ptr = vl[0]
				self.vgmloop_smp = vl[1]
				print vl
	
	# complicated enough?
	# this aims for overall packedness.
	def writespeed(self, spi):
		if spi == 735:
			self.stream.append(0x62)
		elif spi == 882:
			self.stream.append(0x63)
		elif spi <= 16:
			self.stream.append(0x70+spi-1)
		elif spi <= 32:
			self.stream.append(0x7F)
			self.stream.append(0x70+spi-(1+16))
		elif spi == 735+735:
			self.stream.append(0x62)
			self.stream.append(0x62)
		elif spi == 882+882:
			self.stream.append(0x63)
			self.stream.append(0x63)
		elif spi >= 735+1 and spi <= 735+16:
			self.stream.append(0x62)
			self.stream.append(0x70+spi-(735+1))
		elif spi == 882+1 and spi <= 882+16:
			self.stream.append(0x63)
			self.stream.append(0x70+spi-(882+1))
		elif spi <= 65535:
			self.stream.append(0x61)
			self.stream.append(spi&0xFF)
			self.stream.append(spi>>8)
		elif spi <= 65535+882: # this is where it gets a bit silly.
			# don't have to worry about 735.
			# nor do we have to worry about the really small ones.
			self.stream.append(0x61)
			self.stream.append((spi-882)&0xFF)
			self.stream.append((spi-882)>>8)
			self.stream.append(0x63)
		elif spi <= 65535+882+882: # just need a bit more
			self.stream.append(0x61)
			self.stream.append((spi-882-882)&0xFF)
			self.stream.append((spi-882-882)>>8)
			self.stream.append(0x63)
			self.stream.append(0x63)
		else:# ok best just to delegate to writespeed again
			self.stream.append(0x61)
			self.stream.append(0xFF)
			self.stream.append(0xFF)
			self.writespeed(spi-65535)
	
	def loadpat(self, fp, ptr):
		if ptr == 0:
			return (64, [0x00]*64)
		
		fp.seek(ptr)
		l, rows = struct.unpack("<HH", fp.read(4))
		fp.read(4) # skip unused
		return (rows, [ord(c) for c in fp.read(l)] + [0x00]*rows) # pad just in case
	
	def save(self, fname):
		fp = open(fname,"wb")
		fp.write("Vgm ")
		fp.write(struct.pack("<III", 0, 0x150, 3579545))
		loopme = self.vgmloop_ptr != -1
		tagme = True # audacious crashes if we don't have a GD3 tag, even if it's invalid
		fp.write(struct.pack("<IIII", 0, 1, self.streampos, (self.vgmloop_ptr+0x40-0x1C if loopme else 0)))
		fp.write(struct.pack("<IIHBBI", (self.streampos-self.vgmloop_smp if loopme else 0), 50, 0x0009, 16, 0, 0))
		fp.write(struct.pack("<IIII", 0, 0xc, 0, 0))
		print self.vgmloop_ptr+0x40-0x1C, self.streampos-self.vgmloop_smp, self.streampos
		
		fp.write(''.join(chr(c) for c in self.stream))
		fp.write("\x66")
		
		if tagme:
			t = fp.tell()
			fp.seek(0x14)
			fp.write(struct.pack("<I",t-0x14))
			fp.seek(t)
			fp.write("Gd3 \x00\x01\x00\x00\x00\x00\x00\x00")
			t2 = fp.tell()
			for i in xrange(2):
				fp.write(''.join(c+"\x00" for c in self.name+"\x00"))
			for i in xrange(2):
				fp.write(''.join(c+"\x00" for c in "\x00"))
			for i in xrange(2):
				fp.write(''.join(c+"\x00" for c in "Sega Master System\x00"))
			for i in xrange(2):
				fp.write(''.join(c+"\x00" for c in "\x00"))
			fp.write(''.join(c+"\x00" for c in "0000\x00"))
			for i in xrange(2):
				fp.write(''.join(c+"\x00" for c in "\x00"))
			t = fp.tell()
			fp.seek(t2-4)
			fp.write(struct.pack("<I",t-t2))
			
		t = fp.tell()
		fp.seek(0x04)
		fp.write(struct.pack("<I",t-0x04))
		
		fp.close()

IT2VGM(sys.argv[1]).save(sys.argv[2])
