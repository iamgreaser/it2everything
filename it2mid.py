#!/usr/bin/env python --
#
# IT2MID.py by Ben "GreaseMonkey" Russell, 2010, public domain
# Not related to that Russian DOS program which doesn't work very well
# Originally made for a MIDI 1 hour compo and came with a (broken) sample MIDI file.

import struct, sys
from math import *

def nullterm(s):
	return s[:s.index("\x00")] if "\x00" in s else s

def tomid(v):
	s = ""
	hb = 0
	while True:
		s = chr(hb|(v&127)) + s
		v >>= 7
		if not v:
			return s
		hb = 0x80

def midvol(v):
	if v == 0:
		vol = 0
	else:
		vol = 127*log(v)/log(64)
		#vol = int(vol)
	return vol

class Pat:
	def __init__(self, fp, pos):
		if pos == 0:
			self.length = 64
			self.rows = 64
			self.data = [0 for v in xrange(64)]
			return
		fp.seek(pos)
		self.length, self.rows, self.reserved = struct.unpack("<HHI", fp.read(8))
		self.data = [ord(v) for v in fp.read(self.length)]
		#print self.data

class Ins:
	def __init__(self, fp, pos):
		fp.seek(pos)
		fp.read(4) # IMPI
		fp.read(28) # some other crap
		k = fp.read(2)
		if k[1] == " " and k[0] != "\x00" and k[0] != " ":
			self.ch = eval("0x"+k[0])
			self.instype = int(fp.read(3).replace(" ",""))
		else:
			self.ch = -1
			self.instype = -1
		#fp.read(0x1a-5) # rest of name

class MIDI:
	def __init__(self, fname):
		fp = open(fname, "rb")
		if fp.read(4) != "IMPM":
			raise Exception("not an IT file")
		
		self.name = nullterm(fp.read(26))
		self.philite = struct.unpack("<H",fp.read(2))
		self.ordnum, self.insnum, self.smpnum, self.patnum = struct.unpack("<HHHH",fp.read(8))
		self.cvt, self.cwvt, self.crap, self.crap2 = struct.unpack("<HHHH",fp.read(8))
		self.gv, self.mv, self.tpr, self.bpm, self.sep, self.pwd, self.msglen = struct.unpack("<BBBBBBH",fp.read(8))
		self.poffs, self.reserved = struct.unpack("<II",fp.read(8))
		self.cpan = [ord(v) for v in fp.read(64)]
		self.cvol = [ord(v) for v in fp.read(64)]
		self.ords = [ord(v) for v in fp.read(self.ordnum)]
		print self.ords
		print self.insnum, self.smpnum, self.patnum
		self.insoffs = [struct.unpack("<I",fp.read(4)) for i in xrange(self.insnum)]
		self.smpoffs = [struct.unpack("<I",fp.read(4)) for i in xrange(self.smpnum)]
		self.patoffs = [struct.unpack("<I",fp.read(4)) for i in xrange(self.patnum)]
		
		self.inslist = [Ins(fp, self.insoffs[i][0]) for i in xrange(self.insnum)]
		self.patlist = [Pat(fp, self.patoffs[i][0]) for i in xrange(self.patnum)]
		fp.close()
	
	def midev(self, fp, ev):
		fp.write(tomid(self.curtime-self.ntime) + ev)
		self.ntime = self.curtime
	
	def save(self, fname):
		fp = open(fname, "wb")
		fp.write("MThd")
		fp.write(struct.pack(">IHHH", 6,0,1,960))
		fp.write("MTrk")
		mtoffs = fp.tell()
		fp.write("BAD!")
		
		print "let's go"
		
		self.currow = 0
		self.curtick = 0
		self.curord = 0
		self.curpat = self.ords[self.curord]
		self.curpos = 0
		self.curtime = 0
		self.ntime = 0
		self.breakrow = -1
		self.skiprows = 0
		chmask = [0 for i in xrange(64)]
		chdat = [[253,0,255,0,0] for i in xrange(64)]
		lch = [0 for i in xrange(64)]
		ltyp = [0 for i in xrange(64)]
		lnote = [0 for i in xrange(64)]
		cper = [-1 for i in xrange(64)]
		tper = [-1 for i in xrange(64)]
		aper = [0 for i in xrange(64)]
		lins = [-1 for i in xrange(17)]
		chbend = [0 for i in xrange(17)]
		acbend = [0x2000 for i in xrange(17)]
		lbend = [0x2000 for i in xrange(17)]
		chlast = [False for i in xrange(64)]
		vibdat = [0 for i in xrange(64)]
		leff = [[0 for i in xrange(27)] for i in xrange(64)]
		
		# crank that pitch wheel up baby
		for i in xrange(0xB0,0xBF+1,1):
			self.midev(fp,chr(i)+"\x65\x00")
			self.midev(fp,chr(i)+"\x64\x00")
			self.midev(fp,chr(i)+"\x06\x18")
			self.midev(fp,chr(i)+"\x26\x00")
		
		lcell = [[253,0,255,0,0] for i in xrange(64)]
		# blar
		while self.curpat != 0xFF:
			aper = [0 for i in xrange(64)]
			d = self.patlist[self.curpat].data
			if self.curtick == 0:
				lcell = [[253,0,255,0,0] for i in xrange(64)]
				while True:
					while True:
						v = d[self.curpos]
						self.curpos += 1
						if v == 0:
							break
					
						ch = (v&127)-1
						if v & 128:
							chmask[ch] = d[self.curpos]
							self.curpos += 1
					
					
						m = chmask[ch]
						lcell[ch] = n = [253,0,255,0,0]
						if m & 0x01:
							chdat[ch][0] = d[self.curpos]
							self.curpos += 1
						if m & 0x02:
							chdat[ch][1] = d[self.curpos]
							self.curpos += 1
						if m & 0x04:
							chdat[ch][2] = d[self.curpos]
							self.curpos += 1
						if m & 0x08:
							chdat[ch][3] = d[self.curpos]
							self.curpos += 1
							chdat[ch][4] = d[self.curpos]
							self.curpos += 1
					
						if m & 0x11:
							n[0] = chdat[ch][0]
						if m & 0x22:
							n[1] = chdat[ch][1]
						if m & 0x44:
							n[2] = chdat[ch][2]
						if m & 0x88:
							n[3] = chdat[ch][3]
							n[4] = chdat[ch][4]
						
						if self.skiprows:
							continue
						
						if n[0] != 253:
							if n[0] == 254 or n[0] == 255:
								if lnote[ch] != -1:
									self.midev(fp, struct.pack(">BBB",((lch[ch]-1)&0x0F)|0x80,lnote[ch],0))
									lnote[ch] = -1
							elif n[3] == 7 or n[3] == 12:
								tper[ch] = n[0]*64
							else:
								if lnote[ch] != -1:
									self.midev(fp, struct.pack(">BBB",((lch[ch]-1)&0x0F)|0x80,lnote[ch],0))
									lnote[ch] = -1
								ins = self.inslist[n[1]-1]
								if lins[ins.ch] != ins.instype and ins.ch != 0xA:
									lins[ins.ch] = ins
									self.midev(fp, struct.pack(">BB",((ins.ch-1)&0x0F)|0xC0,ins.instype))
								lch[ch] = ins.ch
								ltyp[ch] = ins.instype
								lnote[ch] = n[0]
								tper[ch] = cper[ch] = n[0]*64
								vibdat[ch] = 0
								chbend[lch[ch]] = 0
								vol = 127
								if n[2] <= 64:
									vol = midvol(n[2])
								self.midev(fp, struct.pack(">BBB",((lch[ch]-1)&0x0F)|0x90,lnote[ch],vol))
								#if vol != 127:
								#	self.midev(fp, struct.pack(">BBB",((lch[ch]-1)&0x0F)|0xA0,lnote[ch],vol))
						elif n[2] <= 64:
							vol = midvol(n[2])
							self.midev(fp, struct.pack(">BBB",((lch[ch]-1)&0x0F)|0xA0,lnote[ch],vol))
					
					if not self.skiprows:
						break
					
					self.skiprows -= 1
			
			for ch in xrange(64):
				eft = lcell[ch][3]
				efp = lcell[ch][4]
				el = efp&15
				eh = efp>>4
				
				if efp:
					if eft in [8,9,10]:
						t = efp
						if el == 0:
							t |= (leff[ch][eft] & 0x0F)
						if eh == 0:
							t |= (leff[ch][eft] & 0xF0)
						leff[ch][eft] = t
					else:
						leff[ch][eft] = efp
				
				sfp = leff[ch][eft]
				
				sl = sfp&15
				sh = sfp>>4
				
				# TODO fineslides
				if eft == 1:
					if efp and not self.curtick:
						self.tpr = efp
				elif eft == 3:
					if not self.curtick:
						self.breakrow = efp
				elif eft == 5:
					if self.curtick:
						sfp = leff[ch][7]
						chbend[lch[ch]] -= sfp*4
						cper[ch] -= sfp*4
				elif eft == 6:
					if self.curtick:
						sfp = leff[ch][7]
						chbend[lch[ch]] += sfp*4
						cper[ch] += sfp*4
				elif eft == 7:
					if self.curtick:
						bd = abs(cper[ch] - tper[ch])
						print tper[ch],cper[ch],bd
						if bd > sfp*4:
							bd = sfp*4
						if tper[ch] > cper[ch]:
							chbend[lch[ch]] += bd
							cper[ch] += bd
						elif tper[ch] < cper[ch]:
							chbend[lch[ch]] -= bd
							cper[ch] -= bd
				elif eft == 8:
					aper[ch] = int(sl*sin((pi*vibdat[ch])/128.0)*4)
					vibdat[ch] = (vibdat[ch]+sh*4)&0xFF
				elif eft == 19:
					if sh == 0xB:
						pass # TODO loopback point
					elif sh == 0xC:
						if self.curtick == max(1,sl):
							if lnote[ch] != -1:
								self.midev(fp, struct.pack(">BBB",((lch[ch]-1)&0x0F)|0x80,lnote[ch],0))
								lnote[ch] = -1
					
			
			for ch in xrange(64):
				if aper[ch]:
					chbend[lch[ch]] += aper[ch]
			
			for ch in xrange(1,16+1,1):
				b = min(max(0,0x2000+(chbend[ch]*0x2000)/(64*24)),0x3FFF)
				
				if b != lbend[ch]:
					lbend[ch] = b
					print ch, chbend[ch], chbend[ch]/64
					self.midev(fp, struct.pack(">BBB",((ch-1)&0x0F)|0xE0,b&127,(b>>7)&127))
			
			for ch in xrange(64):
				if aper[ch]:
					chbend[lch[ch]] -= aper[ch]
			
			self.curtime += (960*5)/(self.bpm)
			self.curtick += 1
			if self.curtick >= self.tpr:
				self.curtick = 0
				self.currow += 1
				if self.breakrow != -1 or self.currow >= self.patlist[self.curpat].rows:
					self.curord += 1
					self.curpat = self.ords[self.curord]
					self.curpos = 0
					print "new pat!",self.curord, self.curpat, self.currow
					if self.breakrow != -1:
						self.skiprows = self.currow = self.breakrow
						self.breakrow = -1
					else:
						self.currow = 0
		
		self.midev(fp, "\xFF\x2F\x00")
		
		v = fp.tell()-mtoffs-4
		fp.seek(mtoffs)
		fp.write(struct.pack(">I",v))
		
		print "let's no"
		fp.close()

MIDI(sys.argv[1]).save(sys.argv[2])

