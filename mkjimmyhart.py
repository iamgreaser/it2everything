#
# mkjimmyhart.py - module song modifier
# by Ben "GreaseMonkey" Russell, 2012. Public domain.
#
# usage:
#      python25 mkjimmyhart.py infile.it outfile.it
#
# (i THINK you only need python 2.5. it MUST be python 2.x though.)
#
# module support:
# - .it - ImpulseTracker (supports IT214 - does NOT support embedded MIDI!)
# - .xm - FastTracker 2 (the world could do with less of these)
# - .s3m - Scream Tracker 3 (<3)
# - .mod - SoundTracker and just about every tracker on the Amiga
#
# planned:
# - .rad - Reality ADlib Tracker (<3)
# - .mid - General MIDI (would be fantastic but kinda hard too)
#

import sys, struct, random

def trimnul(s):
	if "\x00" in s:
		s = s[:s.index("\x00")]
	
	return s

def padto(length, s, char="\x00"):
	if len(s) < length:
		s += char*(length-len(s))
	if len(s) > length:
		s = s[:length]
	
	#print length, len(s)
	return s

def alignfp(pt, fp):
	while fp.tell() % pt != 0:
		fp.write("JH"[fp.tell()&1])

class Module:
	tempo = 125
	speed = 6
	name = ""
	
	def __init__(self):
		self.ordlist = []
		self.inslist = []
		self.smplist = []
		self.patlist = []

class ModModule(Module):
	class ModSample:
		def __init__(self):
			pass
		
		def load(self, fp):
			self.name = trimnul(fp.read(22))
			self.length, self.ft, self.vol = (
				struct.unpack(">HBB",fp.read(4)))
			self.lpbeg, self.lplen = (
				struct.unpack(">HH",fp.read(4)))
		
		def loaddata(self, fp):
			self.data = fp.read(self.length*2)
		
		def save(self, fp):
			fp.write(padto(22, self.name))
			fp.write(struct.pack(">HBBHH"
				, self.length, self.ft, self.vol, self.lpbeg, self.lplen))
		
		def savedata(self, fp):
			fp.write(self.data)
	
	class ModPattern:
		rows = 64
		
		def __init__(self):
			pass
		
		def isnote(self, n):
			return n != 0
		
		def load(self, chnnum, fp):
			self.chnnum = chnnum
			
			self.data = []
			#print self.rows, self.chnnum
			for r in xrange(self.rows):
				self.data.append([])
				for c in xrange(self.chnnum):
					p,eft,efp = struct.unpack(">HBB",fp.read(4))
					ins = ((p>>8)&0xF0)|(eft>>4)
					eft &= 0x0F
					p &= 0x0FFF
					self.data[r].append([p,ins,eft,efp])
		
		def save(self, fp):
			for d1 in self.data:
				for p,ins,eft,efp in d1:
					fp.write(struct.pack(">HBB"
						,p|((ins&0xF0)<<8)
						,eft|((ins&15)<<4)
						,efp
							))
	
	def __init__(self):
		Module.__init__(self)
	
	def load(self, fp):
		# format test 1: M.K.
		fp.seek(20+30*31+2+128)
		tag = fp.read(4)
		smp15 = False
		self.tag = None
		
		for v in tag:
			if ord(v) < 0x20 or ord(v) > 0x7E:
				smp15 = True
				break
		
		# format test 2: 0x78
		if smp15:
			fp.seek(20+15*31+1)
			v = fp.read(1)
			if ord(v) != 0x78:
				raise TypeError("not a valid Amiga module")
		
		# now we load this properly.
		fp.seek(0)
		
		self.name = trimnul(fp.read(20))
		self.smplist = []
		
		for i in xrange(15 if smp15 else 31):
			smp = ModModule.ModSample()
			smp.load(fp)
			self.smplist.append(smp)
		
		self.ordnum, self.oldtag = struct.unpack("<BB", fp.read(2))
		self.ordlist = [ord(fp.read(1)) for i in xrange(128)]
		#print self.ordnum, self.oldtag
		self.chnnum = 4
		if not smp15:
			self.tag = fp.read(4)
			
			v0 = ord(self.tag[0])
			v1 = ord(self.tag[1])
			v2 = ord(self.tag[2])
			v3 = ord(self.tag[3])
			if v0 >= 0x30 and v0 <= 0x39:
				if v1 >= 0x30 and v1 <= 0x39:
					self.chnnum = (v0-0x30)*10 + (v1-0x30)
				else:
					self.chnnum = (v0-0x30)
			elif self.tag == "CD81":
				self.chnnum = 8
			elif self.tag == "OCTA":
				self.chnnum = 8
			elif self.tag == "OKTA":
				self.chnnum = 8
			elif self.tag == "FLT8":
				raise Exception("TODO: FLT8 support")
		
		print self.chnnum
		
		self.patnum = 0
		for v in self.ordlist:
			if v > self.patnum:
				self.patnum = v
		self.patnum += 1
		#print self.patnum
		
		self.patlist = []
		for i in xrange(self.patnum):
			pat = ModModule.ModPattern()
			pat.load(self.chnnum, fp)
			self.patlist.append(pat)
		
		for o in self.smplist:
			o.loaddata(fp)
	
	def save(self, fp):
		fp.write(padto(20, self.name))
		for o in self.smplist:
			o.save(fp)
		fp.write(struct.pack("<BB",self.ordnum,self.oldtag))
		for o in self.ordlist:
			fp.write(chr(o))
		if self.tag != None:
			fp.write(self.tag)
		for o in self.patlist:
			o.save(fp)
		for o in self.smplist:
			o.savedata(fp)

class S3MModule(Module):
	class S3MInstrument:
		def __init__(self):
			pass
		
		def load(self, fp):
			self.typ = ord(fp.read(1))
			self.fname = fp.read(12)
			offs  = ord(fp.read(1))<<16
			offs |= ord(fp.read(1))
			offs |= ord(fp.read(1))<<8
			
			self.length, = struct.unpack("<I", fp.read(4))
			self.data1 = fp.read(0x50-0x12)
			
			if self.typ != 1 or offs == 0:
				self.offs = offs
				self.smpdata = None
			else:
				t = fp.tell()
				fp.seek(offs*16)
				self.smpdata = fp.read(self.length)
				fp.seek(t)
		
		def save(self, fp):
			fp.write(chr(self.typ))
			fp.write(padto(12,self.fname))
			self.offssave = fp.tell()
			if self.smpdata == None:	
				fp.write(chr((self.offs>>20)&255))
				fp.write(chr((self.offs>>4)&255))
				fp.write(chr((self.offs>>12)&255))
			else:
				fp.write("\x00\x00\x00")
			
			fp.write(struct.pack("<I",self.length))
			fp.write(self.data1)
			alignfp(16, fp)
		
		def savedata(self, fp):
			if self.smpdata == None:
				return
			
			t1 = fp.tell()
			fp.write(self.smpdata)
			t2 = fp.tell()
			fp.seek(self.offssave)
			fp.write(chr((t1>>20)&255))
			fp.write(chr((t1>>4)&255))
			fp.write(chr((t1>>12)&255))
			fp.seek(t2)
			alignfp(16, fp)
	
	class S3MPattern:
		rows = 64
		chnnum = 32
		
		def isnote(self, n):
			return n < 128
		
		def __init__(self):
			pass
		
		def load(self, fp):
			self.data = [
				[
					[255, 0, 255, 0, 0] for c in xrange(self.chnnum)
				] for r in xrange(self.rows)
			]
			
			fp.read(2) # skip length for now
			
			for r in xrange(self.rows):
				while True:
					m = ord(fp.read(1))
					if not m:
						break
					ch = m & 31
					if m & 0x20:
						self.data[r][ch][0] = ord(fp.read(1))
						self.data[r][ch][1] = ord(fp.read(1))
					if m & 0x40:
						self.data[r][ch][2] = ord(fp.read(1))
					if m & 0x80:
						self.data[r][ch][3] = ord(fp.read(1))
						self.data[r][ch][4] = ord(fp.read(1))
		
		def save(self, fp):
			packdata = ""
			for r in xrange(self.rows):
				for ch in xrange(self.chnnum):
					m = 0x00
					d = self.data[r][ch]
					if d[0] != 255 or d[1] != 0:
						m |= 0x20
					if d[2] != 255:
						m |= 0x40
					if d[3] != 0 or d[4] != 0:
						m |= 0x80
					
					if m == 0:
						continue
					
					packdata += chr(m|ch)
					
					if m & 0x20:
						packdata += chr(d[0])
						packdata += chr(d[1])
					if m & 0x40:
						packdata += chr(d[2])
					if m & 0x80:
						packdata += chr(d[3])
						packdata += chr(d[4])
				
				packdata += "\x00"
			
			fp.write(struct.pack("<H",len(packdata)))
			fp.write(packdata)
			alignfp(16, fp)
					
	
	def __init__(self):
		Module.__init__(self)
	
	def load(self, fp):
		self.name = trimnul(fp.read(28))
		if fp.read(2) != "\x1A\x10":
			raise TypeError("not a valid ST3 module")
		fp.read(2)
		self.ordnum, self.insnum, self.patnum, self.flags = (
			struct.unpack("<HHHH",fp.read(8)))
		self.cwtv, self.ffi = (
			struct.unpack("<HH",fp.read(4)))
		if fp.read(4) != "SCRM":
			# XXX: confirm that this is actually checked in ST3 --GM
			raise TypeError("not a valid ST3 module")
		self.gvol,self.speed,self.tempo,self.mvol,self.uclk,self.usepan = (
			struct.unpack("<BBBBBB",fp.read(6)))
		fp.read(8)
		self.special, = struct.unpack("<H", fp.read(2))
		self.chndata = fp.read(32)
		self.ordlist = [ord(fp.read(1)) for i in xrange(self.ordnum)]
		insoffs = [struct.unpack("<H",fp.read(2))[0] for i in xrange(self.insnum)]
		patoffs = [struct.unpack("<H",fp.read(2))[0] for i in xrange(self.patnum)]
		self.pandata = fp.read(32)
		
		self.inslist = []
		self.patlist = []
		for offs in insoffs:
			if offs == 0:
				self.inslist.append(None)
				continue
			
			t = fp.tell()
			fp.seek(offs*16)
			o = S3MModule.S3MInstrument()
			o.load(fp)
			self.inslist.append(o)
		
		for offs in patoffs:
			if offs == 0:
				self.patlist.append(None)
				continue
			
			t = fp.tell()
			fp.seek(offs*16)
			o = S3MModule.S3MPattern()
			o.load(fp)
			self.patlist.append(o)
	
	def save(self, fp):
		fp.write(padto(28,self.name))
		fp.write("\x1A\x10JH")
		fp.write(struct.pack("<HHHH",
			self.ordnum,self.insnum,self.patnum,self.flags))
		fp.write(struct.pack("<HH",
			self.cwtv,self.ffi))
		fp.write("SCRM")
		fp.write(struct.pack("<BBBBBB",
			self.gvol,self.speed,self.tempo,self.mvol,self.uclk,self.usepan))
		fp.write("mkjh.py;")
		fp.write(struct.pack("<H",self.special))
		fp.write(self.chndata)
		for v in self.ordlist:
			fp.write(chr(v))
		ptrbase = fp.tell()
		fp.write("\x00\x00"*(self.insnum+self.patnum))
		fp.write(self.pandata)
		i = 0
		dump = []
		alignfp(16, fp)
		for o in self.inslist+self.patlist:
			if o != None:
				alignfp(16,fp)
				t1 = fp.tell()
				o.save(fp)
				t2 = fp.tell()
				fp.seek(ptrbase+i*2)
				fp.write(struct.pack("<H",t1>>4))
				fp.seek(t2)
			i += 1
		for o in self.inslist:
			if o != None:
				o.savedata(fp)
		
class XMModule(Module):
	class XMPattern:
		def __init__(self):
			pass
		
		def isnote(self, nval):
			return nval >= 1 and nval <= 96
		
		def load(self, chnnum, fp):
			headlen, = struct.unpack("<I", fp.read(4))
			head = padto(5, fp.read(max(0,headlen-4)))
			ptype, self.rows, psize = struct.unpack("<BHH", head)
			self.chnnum = chnnum
			
			if self.rows == 0:
				self.rows = 64
			
			data = [ord(v) for v in fp.read(psize)]
			
			self.data = [
				[
					[0,0,0,0,0] for c in xrange(self.chnnum)
				] for r in xrange(self.rows)
			]
			
			for r in xrange(self.rows):
				for c in xrange(self.chnnum):
					if not data:
						break
					
					v = data.pop(0)
					if v & 0x80:
						if len(data) < 5:
							data += [0]*(4-len(data))
						
						if v & 0x01:
							self.data[r][c][0] = data.pop(0)
						if v & 0x02:
							self.data[r][c][1] = data.pop(0)
						if v & 0x04:
							self.data[r][c][2] = data.pop(0)
						if v & 0x08:
							self.data[r][c][3] = data.pop(0)
						if v & 0x10:
							self.data[r][c][4] = data.pop(0)
					else:
						self.data[r][c][0] = v
						if len(data) < 4:
							data += [0]*(4-len(data))
						self.data[r][c][1] = data.pop(0)
						self.data[r][c][2] = data.pop(0)
						self.data[r][c][3] = data.pop(0)
						self.data[r][c][4] = data.pop(0)
						
		
		def save(self, fp):
			if self.rows == 64:
				blank = True
				
				for r in xrange(self.rows):
					for c in xrange(self.chnnum):
						for v in self.data[r][c]:
							if v != 0:
								blank = False
								break
				
				if blank:
					fp.write("\x00"*4)
					return
			
			packdata = ""
			
			for r in xrange(self.rows):
				for c in xrange(self.chnnum):
					m = 0x00
					d = self.data[r][c]
					if d[0]:
						m |= 0x01
					if d[1]:
						m |= 0x02
					if d[2]:
						m |= 0x04
					if d[3]:
						m |= 0x08
					if d[4]:
						m |= 0x10
					
					if m != 0x1F:
						packdata += chr(0x80|m)
					
					if m & 0x01:
						packdata += chr(d[0])
					if m & 0x02:
						packdata += chr(d[1])
					if m & 0x04:
						packdata += chr(d[2])
					if m & 0x08:
						packdata += chr(d[3])
					if m & 0x10:
						packdata += chr(d[4])
			
			fp.write(struct.pack("<IBHH",9,0,self.rows,len(packdata)))
			fp.write(packdata)
	
	class XMSample:
		def __init__(self):
			pass
		
		def load(self, smphsize, fp):
			head = padto(18+22, fp.read(smphsize))
			self.length, = struct.unpack("<I", head[:4])
			self.data1 = head[4:18]
			flg = ord(head[14])
			self.name = trimnul(head[18:])
			print self.length, repr(self.data1), repr(self.name)
		
		def loaddata(self, fp):
			print self.length
			self.smpdata = fp.read(self.length)
		
		def save(self, smphsize, fp):
			head = struct.pack("<I", self.length)
			head += self.data1
			head += padto(22, self.name)
			fp.write(padto(smphsize, head))
		
		def savedata(self, fp):
			fp.write(self.smpdata)
	
	class XMInstrument:
		def __init__(self):
			pass
		
		def load(self, fp):
			isize, = struct.unpack("<I",fp.read(4))
			print "ins", isize
			idata = padto(263-4, fp.read(max(0,isize-4)))
			self.name = trimnul(idata[:22])
			self.itype, self.smpnum, self.smphsize = (
				struct.unpack("<BHI",idata[22:33-4]))
			print "smp", self.smpnum, self.smphsize, self.itype
			self.data1 = idata[33-4:]
			
			self.smplist = []
			for i in xrange(self.smpnum):
				smp = XMModule.XMSample()
				smp.load(self.smphsize, fp)
				self.smplist.append(smp)
			
			for o in self.smplist:
				o.loaddata(fp)
		
		def save(self, fp):
			fp.write(struct.pack("<I", 263))
			fp.write(padto(22, self.name))
			fp.write(struct.pack("<BHI",
				self.itype, self.smpnum, self.smphsize))
			fp.write(self.data1)

			for o in self.smplist:
				o.save(self.smphsize, fp)
			
			for o in self.smplist:
				o.savedata(fp)
	
	def __init__(self):
		Module.__init__(self)
	
	def load(self, fp):
		if fp.read(17) != "Extended Module: ":
			raise TypeError("not an extended module")
		self.name = trimnul(fp.read(20))
		if fp.read(1) != "\x1A":
			raise TypeError("not an extended module")
		self.trkname = trimnul(fp.read(20))
		self.ver, hsize = struct.unpack("<HI", fp.read(6))
		header = padto(2*8+256, fp.read(max(0,hsize-4)))
		self.ordnum, self.respos, self.chnnum, self.patnum = (
			struct.unpack("<HHHH",header[:2*4]))
		self.insnum, self.flags, self.speed, self.tempo = (
			struct.unpack("<HHHH",header[2*4:][:2*4]))
		self.ordlist = [ord(v) for v in header[-256:]]
		
		self.patlist = []
		self.inslist = []
		for i in xrange(self.patnum):
			o = XMModule.XMPattern()
			o.load(self.chnnum, fp)
			self.patlist.append(o)
		for i in xrange(self.insnum):
			o = XMModule.XMInstrument()
			o.load(fp)
			self.inslist.append(o)
	
	def save(self, fp):
		fp.write("Extended Module: ")
		fp.write(padto(20, self.name))
		fp.write("\x1A")
		fp.write(padto(20, "mkjimmyhart.py"))
		fp.write(struct.pack("<HI", self.ver, 2*8+256+4))
		fp.write(struct.pack("<HHHH",
			self.ordnum, self.respos, self.chnnum, self.patnum))
		fp.write(struct.pack("<HHHH",
			self.insnum, self.flags, self.speed, self.tempo))
		for v in self.ordlist:
			fp.write(chr(v))
		
		for o in self.patlist:
			o.save(fp)
		for o in self.inslist:
			o.save(fp)

class ITModule(Module):
	class ITInstrument:
		def __init__(self):
			pass
		
		def load(self, fp):
			self.data = padto(554, fp.read(554))
		
		def save(self, fp):
			fp.write(self.data)
	
	class ITSample:
		def __init__(self):
			pass
		
		def load(self, fp):
			self.data1 = padto(72, fp.read(72))
			offs, = struct.unpack("<I",fp.read(4))
			length, = struct.unpack("<I",self.data1[0x30:][:4])
			
			flg = ord(self.data1[0x12])
			self.data2 = padto(4, fp.read(4))
			t = fp.tell()
			fp.seek(offs)
			if not (flg & 0x01):
				self.smpdata = None
			elif flg & 0x08:
				# compressed sample
				if flg & 0x02: # 16-bit
					length *= 2
				bcount = ((length+0x7FFF)//0x8000)+1
				if flg & 0x04: # stereo
					bcount *= 2
				length = 0
				self.smpdata = ""
				for i in xrange(bcount):
					s = fp.read(2)
					blen, = struct.unpack("<H",s)
					self.smpdata += s
					self.smpdata += fp.read(blen)
					length += blen+2
			else:
				# uncompressed
				if flg & 0x02: # 16-bit
					length *= 2
				if flg & 0x04: # stereo
					length *= 2
				self.smpdata = fp.read(length)
			
			fp.seek(t)
		
		def save(self, fp):
			fp.write(self.data1)
			fp.write("\x00"*4 if self.smpdata == None
				else struct.pack("<I",fp.tell()+8))
			
			fp.write(self.data2)
			if self.smpdata != None:
				fp.write(self.smpdata)
	
	class ITPattern:
		rows = 64
		chnnum = 64
		def __init__(self):
			pass
		
		def isnote(self, nval):
			return nval < 120
		
		def load(self, fp):
			if fp == None:
				self.rows = 64
			else:
				length, self.rows, _ = struct.unpack("<HHI",fp.read(8))
			
			self.data = [
				[
					[253,0,255,0,0] for c in xrange(64)
				] for r in xrange(self.rows)
			]
			
			if fp == None:
				return
			
			lmask = [0 for i in xrange(64)]
			lval = [[253,0,255,0,0] for i in xrange(64)]
			for r in xrange(self.rows):
				while True:
					cval = ord(fp.read(1))
					if cval == 0:
						break
					
					ch = (cval & 127)-1
					if cval & 0x80:
						lmask[ch] = ord(fp.read(1))
					
					m = lmask[ch]
					
					if m & 0x01:
						lval[ch][0] = ord(fp.read(1))
					if m & 0x02:
						lval[ch][1] = ord(fp.read(1))
					if m & 0x04:
						lval[ch][2] = ord(fp.read(1))
					if m & 0x08:
						lval[ch][3] = ord(fp.read(1))
						lval[ch][4] = ord(fp.read(1))
					
					if m & 0x11:
						self.data[r][ch][0] = lval[ch][0]
					if m & 0x22:
						self.data[r][ch][1] = lval[ch][1]
					if m & 0x44:
						self.data[r][ch][2] = lval[ch][2]
					if m & 0x88:
						self.data[r][ch][3] = lval[ch][3]
						self.data[r][ch][4] = lval[ch][4]
		
		def save(self, fp):
			packdata = ""
			lmask = [0 for i in xrange(64)]
			lval = [[253,0,255,0,0] for i in xrange(64)]
			for r in xrange(self.rows):
				for c in xrange(64):
					m = 0x00
					if self.data[r][c][0] != 253:
						if self.data[r][c][0] == lval[c][0]:
							m |= 0x10
						else:
							m |= 0x01
					if self.data[r][c][1] != 0:
						if self.data[r][c][1] == lval[c][1]:
							m |= 0x20
						else:
							m |= 0x02
					if self.data[r][c][2] != 255:
						if self.data[r][c][2] == lval[c][2]:
							m |= 0x40
						else:
							m |= 0x04
					if self.data[r][c][3] != 0 or self.data[r][c][4] != 0:
						if self.data[r][c][3] == lval[c][3] and (
								self.data[r][c][4] == lval[c][4]):
							m |= 0x80
						else:
							m |= 0x08
					
					if m == 0:
						continue
					
					if m == lmask[c]:
						packdata+=(chr(c+1))
					else:
						lmask[c] = m
						packdata+=(chr((c+1)|0x80))
						packdata+=(chr(m))
					
					if m & 0x01:
						packdata+=(chr(self.data[r][c][0]))
					if m & 0x02:
						packdata+=(chr(self.data[r][c][1]))
					if m & 0x04:
						packdata+=(chr(self.data[r][c][2]))
					if m & 0x08:
						packdata+=(chr(self.data[r][c][3]))
						packdata+=(chr(self.data[r][c][4]))
				
				packdata+=(chr(0))
			
			fp.write(struct.pack("<HH", len(packdata), self.rows))
			fp.write("J.H.")
			fp.write(packdata)
	
	def __init__(self):
		Module.__init__(self)
	
	def load(self, fp):
		if fp.read(4) != "IMPM":
			raise TypeError("not an IMPM module")
		
		self.name = trimnul(fp.read(25))
		fp.read(1)
		self.pathl, self.ordnum, self.insnum, self.smpnum, self.patnum = (
			struct.unpack("<HHHHH", fp.read(10)))
		self.cwtv, self.cmwt, self.flags, self.special = (
			struct.unpack("<HHHH", fp.read(8)))
		self.gvol, self.mvol, self.speed, self.tempo, self.sep, self.pwd = (
			struct.unpack("<BBBBBB", fp.read(6)))
		msglen, msgoffs, self.timestamp = (
			struct.unpack("<HII", fp.read(10)))
		self.chnpan = [ord(fp.read(1)) for i in xrange(64)]
		self.chnvol = [ord(fp.read(1)) for i in xrange(64)]
		self.ordlist = [ord(fp.read(1)) for i in xrange(self.ordnum)]
		insoffs = [struct.unpack("<I",fp.read(4))[0] for i in xrange(self.insnum)]
		smpoffs = [struct.unpack("<I",fp.read(4))[0] for i in xrange(self.smpnum)]
		patoffs = [struct.unpack("<I",fp.read(4))[0] for i in xrange(self.patnum)]
		self.inslist = []
		self.smplist = []
		self.patlist = []
		
		for offs in insoffs:
			if offs == 0:
				self.inslist.append(None)
			else:
				fp.seek(offs)
				ins = ITModule.ITInstrument()
				ins.load(fp)
				self.inslist.append(ins)
		
		for offs in smpoffs:
			if offs == 0:
				self.smplist.append(None)
			else:
				fp.seek(offs)
				smp = ITModule.ITSample()
				smp.load(fp)
				self.smplist.append(smp)
		
		for offs in patoffs:
			if offs == 0:
				self.patlist.append(None)
			else:
				fp.seek(offs)
				pat = ITModule.ITPattern()
				pat.load(fp)
				self.patlist.append(pat)
		
		if (self.special & 0x01) and msgoffs != 0 and msglen != 0:
			fp.seek(msgoffs)
			self.msg = fp.read(msglen)
		else:
			self.msg = None
	
	def save(self, fp):
		fp.write("IMPM")
		fp.write(padto(25,self.name))
		fp.write("\x00")
		fp.write(struct.pack("<HHHHH",
			self.pathl,self.ordnum,self.insnum,self.smpnum,self.patnum))
		fp.write(struct.pack("<HHHH",
			self.cwtv,self.cmwt,self.flags,self.special))
		fp.write(struct.pack("<BBBBBB",
			self.gvol, self.mvol, self.speed, self.tempo, self.sep, self.pwd))
		fp.write(struct.pack("<HI",
			len(self.msg) if self.msg != None else 0, 0))
		fp.write("J.H.")
		for v in self.chnpan:
			fp.write(chr(v))
		for v in self.chnvol:
			fp.write(chr(v))
		for v in self.ordlist:
			fp.write(chr(v))
		
		startins = fp.tell()
		for v in self.inslist:
			fp.write("\x00"*4)
		startsmp = fp.tell()
		for v in self.smplist:
			fp.write("\x00"*4)
		startpat = fp.tell()
		for v in self.patlist:
			fp.write("\x00"*4)
		
		fp.write("\x00"*6)
		
		# message
		if self.msg != None:
			t1 = fp.tell()
			fp.write(self.msg)
			t2 = fp.tell()
			fp.seek(0x0036)
			fp.write(struct.pack("<HI",len(self.msg),t1))
			fp.seek(t2)
		
		# other stuff
		i = 0
		for o in self.inslist + self.smplist + self.patlist:
			if o != None:
				t1 = fp.tell()
				o.save(fp)
				t2 = fp.tell()
				fp.seek(startins+4*i)
				fp.write(struct.pack("<I",t1))
				fp.seek(t2)
			i += 1
		

# find a module class that can load your module
MODULE_CLASSES = [ITModule, XMModule, S3MModule, ModModule]

ok = False

print "Loading"
fp = open(sys.argv[1],"rb")
for cls in MODULE_CLASSES:
	try:
		mod = cls()
		fp.seek(0)
		mod.load(fp)
		fp.close()
		ok = True
		break
	except TypeError, e:
		print e
		continue

if not ok:
	print "ERROR: Could not load module!"
	sys.exit(1)

print "Success! Now modifying pattern data."

# modify the pattern data
for pat in mod.patlist:
	if pat == None:
		continue
	
	print pat.rows
	
	for c in xrange(pat.chnnum):
		for r in xrange(4):
			lpos = -1
			ldata = None
			usedins = [False for i in xrange(256)]
			for j in xrange(pat.rows):
				d = pat.data[j][c]
				if d[1] != 0 and not usedins[d[1]]:
					curins = d[1]
					usedins[d[1]] = True
					for i in xrange(pat.rows):
						d = pat.data[i][c]
						if pat.isnote(d[0]) and d[1] == curins:
							if ldata != None:
								ck1 = (d[1]==0 or d[1]==0 or ldata[1]==d[1])
								if ck1 and random.random() < 0.3:
									n0 = ldata[0]
									n1 = d[0]
									d[0] = n0
									ldata[0] = n1
									# should this be used? --GM
									d, ldata = ldata, d
							
					
							ldata = d
							lpos = i
			

# save
print "Saving"
fp = open(sys.argv[2],"wb")
mod.save(fp)
print "Done!"
