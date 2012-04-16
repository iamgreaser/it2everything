# -*- coding: utf-8 -*-
#
# NOTE: This is an experimental hack of pymod.py.
# If you have any suggestions, please poke me. Thanks.
#
# Python MOD player by Ben "GreaseMonkey" Russell
#
# NOW IN STEREO
#
# Designed on FreeBSD 7.2-STABLE with the newpcm driver.
# This means that I can get away with using OSS
# as it doesn't hog the audio.
#
# I release this to the public domain. Fire at will.
#
# NEW: Support for that sad sack of a sound API, winsound.
# NEWER: E8x effect supported PROPERLY (HINT IT'S NOT PANNING)
#        (it's also quite slow)

import math, sys, time, random
try:
	import ossaudiodev
except ImportError:
	ossaudiodev = None
	print "Dear Python developers:"
	print "GET A DECENT SOUND API FOR THE WINDOWS GUYS."
	print "Attempting to use winsound. Give me J2ME any day."
	import winsound
	import threading

# 10^9 / (70*4).
# TODO: shove an actual NTSC or PAL clock in.
# t_o_t.mod might cope better with this, though.
global AMICLK
AMICLK = 3571428.571

# This enables STEREO.
# Turn it on if you like stereo.
# Turn if off if your computer sucks or isn't up to scratch.
# (I suggest you try having it on first.)
global STEREO
STEREO = True

# This jerks with the filter.
# Setting it to "on" will toggle the filter at row 30 each time.
global HAPPYFUNTEST
HAPPYFUNTEST = False

# This one makes Karplus-Strong synthesis occur EVERY ROW.
global HAPPYFUNTESTTWO
HAPPYFUNTESTTWO = False

# This enables the displayish thingy.
# Turn it off if you don't want the patterns displayed.
# Turn it on if you want to find out why this sucks, if that's the case.
global DISPLAYISHTHINGY
DISPLAYISHTHINGY = True

# If you don't want to play LOW "out of range" notes, enable this.
# These are hypothetically playable on real hardware.
# Note that high "out of range" notes will always be clamped due to the way this player works.
global CLAMP_LOW_NOTES
CLAMP_LOW_NOTES = False

# Kudos to bubsy for this valuable piece of info.
global IVLTAB
IVLTAB = [
	0,5,6,7,8,10,11,13,16,19,22,26,32,43,64,128
]

global FTTAB
FTTAB = [
	1712,1700,1687,1675,1663,1651,1639,1628,
	1814,1801,1788,1775,1762,1749,1737,1724,
]

class VibTabRandomiser:
	def __getitem__(self, idx):
		return random.randint(-64,64)

global VIBTAB
VIBTAB = [
	[
		int(math.sin(3.14159265358979*i/32)*64) for i in xrange(64)
	] , 
	[
		int(64-(i*2)) for i in xrange(64)
	] ,
	[
		64 if i < 32 else -64 for i in xrange(64)
	] ,
	VibTabRandomiser()
]

global ARPUP
ARPUP = [
	1712,1616,1525,1440,1359,1283,1211,1143,
	1078,1018, 961, 907, 856, 808, 763, 720,
]

global SUBPERBASE
SUBPERBASE = 1712

def u8be(fp):
	z = fp.read(1)
	if not z:
		return 0
	return ord(z)

def u16be(fp):
	return (u8be(fp)<<8)+u8be(fp)

def tou8le(v):
	return chr(v & 255)

def tosign8(v):
	return v if v < 0x80 else v-0x100

def tou16le(v):
	return tou8le(v)+tou8le(v>>8)

def tou32le(v):
	return tou16le(v)+tou16le(v>>16)

# Only necessary for winsound users.
global wincrapobj

class GlobalWinCrap:
	def __init__(self):
		self.shutup = False
		self.wincraparr = []
		self.wincrapsize = 0
		self.wavqueue = []
		self.sema_access = threading.Semaphore(1)
		self.sema_run = threading.Semaphore(1)
		self.sema_queue = threading.Semaphore(5)
		
		self.thread = None
	
	def play_wincrap(self, arr, dspspeed):
		if self.shutup:
			return
		self.sema_access.acquire()
		self.wincrapsize += len(arr)
		self.wincraparr.append(arr)
		
		if self.wincrapsize < dspspeed*3:
			self.sema_access.release()
			return
		
		farr = self.wincraparr.pop(0)
		while self.wincraparr:
			farr.extend(self.wincraparr.pop(0))
		
		smp = (
			'RIFF'+tou32le(self.wincrapsize+36)+'WAVEfmt '+tou32le(16)
				+tou16le(1) # type: PCM
				+tou16le(2 if STEREO else 1) # channels: 1
				+tou32le(dspspeed) # frequency: [dspspeed]
				+tou32le(dspspeed*(2 if STEREO else 1)*(8/8)) # byte rate
				+tou16le((2 if STEREO else 1)*(8/8)) # block align
				+tou16le(8) # bits per sample
				+'data'+tou32le(self.wincrapsize)
				+''.join(chr(c) for c in farr)
		)
		
		self.wincrapsize = 0
		self.wincraparr = []
		
		self.sema_run.acquire()
		
		if not self.thread:
			self.thread = threading.Thread(None, self.runthread)
			self.thread.start()
		self.wavqueue.append(smp)
		self.sema_run.release()
		self.sema_queue.acquire()
		
		
		self.sema_access.release()
	
	def runthread(self):
		while not self.shutup:
			self.sema_run.acquire()
			if self.wavqueue:
				wav = self.wavqueue.pop(0)
				self.sema_queue.release()
			else:
				break
			self.sema_run.release()
			
			winsound.PlaySound(wav, winsound.SND_MEMORY)
		
		self.thread = None
		self.sema_run.release()
		

if ossaudiodev:
	wincrapobj = None
else:
	wincrapobj = GlobalWinCrap()

def play_wincrap(arr, dspspeed):
	global wincrapobj
	
	wincrapobj.play_wincrap(arr, dspspeed)

class ModSample:
	def __init__(self, fp):
		self.name = fp.read(22).replace("\x00"," ")
		for i in xrange(32):
			self.name = self.name.replace(chr(i),"*")
		self.length = u16be(fp)<<1
		self.ft = FTTAB[u8be(fp) & 0xF]
		self.vol = u8be(fp)
		self.lpbeg = u16be(fp)<<1
		self.lplen = u16be(fp)<<1
		if self.lplen == 2:
			self.lplen = 0
	
	def loadwf(self, fp):
		self.data = [tosign8(u8be(fp)) for i in xrange(self.length)]
		if self.length:
			#print self.data
			if self.lplen:
				print self.lpbeg, self.lplen, self.length
				if self.lpbeg + self.lplen > self.length:
					print "Correcting loop length"
					self.lplen = self.length - self.lpbeg
				self.data += [self.data[self.lpbeg+i] for i in xrange(self.lplen)]
				for i in xrange(2500):
					self.data.append(self.data[-self.lplen])
			else:
				self.data += [0 for i in xrange(2500)]
	
	def funkit(self, pos):
		if not self.lplen:
			return
		self.data[self.lpbeg+pos] = -1-self.data[self.lpbeg+pos]
		pos += self.length
		q = self.length+self.lplen+2500
		while pos < q:
			self.data[pos] = -1-self.data[pos]
			pos += self.lplen
	
	def karplusstrong(self):
		if not self.lplen:
			return
		
		v1 = self.data[self.lpbeg]
		for i in xrange(1,self.lplen,1):
			v2 = self.data[self.lpbeg+i]
			self.data[self.lpbeg+i] = (v1+v2)/2
			v1 = v2
		
		v2 = self.data[self.lpbeg]
		self.data[self.lpbeg+self.lplen-1] = (v1+v2)/2
		
		p = self.lpbeg
		q = self.length
		r = self.length+self.lplen+2500
		# Copy loop data to end.
		for i in xrange(self.lplen):
			self.data[q] = self.data[p]
			p += 1
			q += 1
		p = self.length
		while q < r:
			self.data[q] = self.data[p]
			p += 1
			q += 1
		

class ModCell:
	def __init__(self, fp):
		pdat1 = u16be(fp)
		pdat2 = u16be(fp)
		self.smp    = (pdat1>>8) & 0xF0
		self.smp   |= (pdat2>>12) & 0xF
		self.period     = pdat1 & 0xFFF
		self.efftype = (pdat2>>8) & 0xF
		self.effparam    = pdat2 & 0xFF
		
		if self.period:
			if self.period < 113:
				self.period = 113
			elif CLAMP_LOW_NOTES and self.period > 856:
				self.period = 856

class ModPattern:
	def __init__(self, fp, chn, flt8):
		self.data = []
		for r in xrange(64):
			self.data.append([])
			for c in xrange(chn):
				if flt8 and c >= 4:
					self.data[-1].append(self.data[-1][-4])
				else:
					self.data[-1].append(ModCell(fp))
	
	def flt8merge(self, pat2):
		for r in xrange(64):
			for c in xrange(4):
				self.data[r][c+4] = pat2.data[r][c]


class ModChannel:
	def __init__(self, parent, pan):
		self.latchsmp = None
		self.playsmp = None
		self.vol = 0
		self.offs = 0
		self.suboffs = 0
		self.finetune = 0
		self.period = 0
		self.cperiod = 0
		self.qcell = None
		self.cell = None
		self.parent = parent
		self.data = None
		self.eff_vol = 0
		self.eff_slide = 0
		self.eff_porta = 0
		self.eff_vibspeed = 0
		self.eff_vibdepth = 0
		self.eff_trmspeed = 0
		self.eff_trmdepth = 0
		self.eff_vibpos = 0
		self.eff_trmpos = 0
		self.eff_vibmode = 0
		self.eff_trmmode = 0
		self.eff_vibretrig = True
		self.eff_trmretrig = True
		self.eff_lbkpos = -1
		self.eff_lbkcount = 0
		self.eff_ivlspeed = 0
		self.eff_ivlpos = 0
		self.eff_ivlwpos = 0
		self.eff_rowtick = 0
		self.defpan = self.pan = pan
		# TODO test the 9xx then note w/o ins quirk
		# and possibly add support for the 2x offset bug
		self.baseoffs = 0
		self.eff_ivlon = False
		
		self.q1 = self.q2 = 0.0
	
	def set_stuff(self, cell, usedel=True):
		if usedel and cell.efftype == 0xE and (cell.effparam & 0xF0) == 0xD0:
			self.qcell = cell
			self.cell = None
			return
		
		self.cell = cell
		
		if cell.smp:
			self.latchsmp = self.parent.smplist[cell.smp-1]
		
		if (cell.efftype != 0xE or ((cell.effparam & 0xF0) != 0xF0)
				or not (cell.effparam & 0xF)):
			if cell.smp:
				self.vol = self.latchsmp.vol
				self.eff_vol = 0
				self.baseoffs = 0
			if cell.period:
				self.kicknote(cell)
	
	def kicknote(self, cell):
		if cell.period:
			self.period = (cell.period*self.latchsmp.ft)/1712
			if self.period < 113:
				self.period = 113
			elif CLAMP_LOW_NOTES and self.period > 856:
				self.period = 856
		if cell.efftype != 0xE or (cell.effparam & 0xF0) != 0xF0 or not (cell.effparam & 0xF):
			pass
		elif cell.smp:
			self.vol = self.latchsmp.vol
			self.eff_vol = 0
			self.baseoffs = 0
		
		self.eff_ivlwpos = 0
		
		if self.latchsmp:
			if (cell.efftype != 0x3 and cell.efftype != 0x5) or not self.cperiod or not self.playsmp:
				if self.eff_vibretrig:
					self.eff_vibpos = 0
				if self.eff_trmretrig:
					self.eff_vibpos = 0
				self.offs = self.baseoffs
				self.suboffs = 0
				self.cperiod = self.period
				
				# assuming this has vague semblance to FartTracker?
				# please correct me if this atroscity doesn't.
				self.pan = self.defpan
				
				self.playsmp = self.latchsmp
				self.data = self.playsmp.data

	def eff_slide_vol(self, tick, eph, epl):
		if epl and eph:
			return
		
		if tick:
			self.vol += self.eff_vol
			if self.vol < 0:
				self.vol = 0
			elif self.vol > 64:
				self.vol = 64
		else:
			if epl:
				self.eff_vol = -epl
			else:
				self.eff_vol = eph
	
	def eff_slide_down(self, tick, ep):
		if tick:
			self.cperiod += self.eff_slide
			if self.cperiod > 856:
				self.cperiod = 856
			self.tperiod = self.cperiod
		elif ep:
			self.eff_slide = ep
	
	def eff_slide_up(self, tick, ep):
		if tick:
			self.cperiod -= self.eff_slide
			if self.cperiod < 113:
				self.cperiod = 113
			self.tperiod = self.cperiod
		elif ep:
			self.eff_slide = ep
	
	def eff_slide_porta(self, tick, ep):
		if tick:
			if self.cperiod > self.period:
				self.cperiod -= self.eff_porta
				if self.cperiod < self.period:
					self.cperiod = self.period
			elif self.cperiod < self.period:
				self.cperiod += self.eff_porta
				if self.cperiod > self.period:
					self.cperiod = self.period
			self.tperiod = self.cperiod
		elif ep:
			self.eff_porta = ep
	
	def eff_vibrato(self, tick, eph, epl):
		vd = VIBTAB[self.eff_vibmode][self.eff_vibpos]*self.eff_vibdepth
		self.tperiod += vd/64
		if self.tperiod < 113:
			self.tperiod = 113
		elif self.tperiod > 856:
			self.tperiod = 856
		self.eff_vibpos = (self.eff_vibpos + self.eff_vibspeed) & 63
		
		if (eph or epl) and not tick:
			self.eff_vibspeed = eph
			self.eff_vibdepth = epl
	
	def eff_tremolo(self, tick, eph, epl):
		if tick:
			vd = VIBTAB[self.eff_trmmode][self.eff_trmpos]*self.eff_trmdepth
			self.tvol += vd/16
			if self.tvol < 0:
				self.tvol = 0
			elif self.tvol > 64:
				self.tvol = 64
			self.eff_trmpos = (self.eff_trmpos + self.eff_trmspeed) & 63
		elif eph or epl:
			self.eff_trmspeed = eph
			self.eff_trmdepth = epl
	
	def tick_stuff(self, tick):
		if not self.cell:
			# assume only EDx
			if self.qcell and (self.qcell.effparam & 15) == tick:
				self.set_stuff(self.qcell, False)
				self.qcell = None
			else:
				return
		
		if HAPPYFUNTESTTWO and not tick:
			if self.latchsmp:
				self.latchsmp.karplusstrong()
		
		self.tperiod = self.cperiod
		self.tvol = self.vol
		et = self.cell.efftype
		ep = self.cell.effparam
		eph = ep>>4
		epl = ep&15
		
		if et == 0xE:
			# In case you haven't noticed, nobody ever uses the filter.
			# But nevertheless, we'll implement that awful thing anyway.
			if eph == 0x0:
				if epl < 0x2 and not tick:
					self.parent.filteron = epl != 0x1
			elif eph == 0x1:
				if not tick:
					self.cperiod -= epl
					if self.cperiod < 113:
						self.cperiod = 113
					self.tperiod = self.cperiod
			elif eph == 0x2:
				if not tick:
					self.cperiod += epl
					if self.cperiod > 856:
						self.cperiod = 856
					self.tperiod = self.cperiod
			elif eph == 0x3:
				# TODO glissando
				pass
			elif eph == 0x4:
				self.eff_vibmode = epl & 3
				self.eff_vibretrig = (epl & 4) == 0
			elif eph == 0x5:
				if self.latchsmp:
					self.latchsmp.ft = FTTAB[epl]
				pass
			elif eph == 0x6:
				if not tick:
					if epl:
						if self.eff_lbkcount:
							self.eff_lbkcount -= 1
						else:
							self.eff_lbkcount = epl
						if self.eff_lbkcount:
							self.parent.hasbumped = True
							self.parent.currow = self.eff_lbkpos
					else:
						self.eff_lbkpos = self.parent.currow_real
					
			elif eph == 0x7:
				self.eff_trmmode = epl & 3
				self.eff_trmretrig = (epl & 4) == 0
			elif eph == 0x8:
				# don't smoke this crap
				if not tick:
					#self.pan = epl*0x11  # SOD OFF YOU HERETIC
					if self.latchsmp:
						self.latchsmp.karplusstrong()
			elif eph == 0x9:
				# TODO find out what happens when epl == 0
				if tick and not (tick % max(1,epl)):
					self.kicknote(self.cell)
			elif eph == 0xA:
				if not tick:
					self.vol += epl
					if self.vol > 64:
						self.vol = 64
					self.tvol = self.vol
			elif eph == 0xB:
				if not tick:
					self.vol -= epl
					if self.vol < 0:
						self.vol = 0
					self.tvol = self.vol
			elif eph == 0xC:
				if tick == epl:
					self.tvol = self.vol = 0
			elif eph == 0xD:
				# handled elsewhere
				pass
			elif eph == 0xE:
				if tick == self.parent.tpr-1:
					if self.eff_rowtick:
						self.eff_rowtick -= 1
					else:
						self.eff_rowtick = epl
					if self.eff_rowtick:
						self.parent.curtick = -1
			elif eph == 0xF:
				# emax-doz.mod uses this and it needs it badly
				# really, it's just so much more epic with this thing
				if not tick:
					self.eff_ivlspeed = IVLTAB[epl]
					if not self.eff_ivlspeed:
						self.eff_ivlwpos = 0
		elif et == 0x0:
			if ep:
				t = tick % 3
				if t == 1 and eph:
					self.tperiod = (self.cperiod * ARPUP[eph]) / 1712
				elif t == 2 and epl:
					self.tperiod = (self.cperiod * ARPUP[epl]) / 1712
				else:
					self.tperiod = self.cperiod
		elif et == 0x1:
			self.eff_slide_up(tick, ep)
		elif et == 0x2:
			self.eff_slide_down(tick, ep)
		elif et == 0x3:
			self.eff_slide_porta(tick, ep)
		elif et == 0x4:
			self.eff_vibrato(tick, eph, epl)
		elif et == 0x5:
			self.eff_slide_porta(tick, 0)
			self.eff_slide_vol(tick, eph, epl)
		elif et == 0x6:
			self.eff_vibrato(tick, 0, 0)
			self.eff_slide_vol(tick, eph, epl)
		elif et == 0x7:
			self.eff_tremolo(tick, 0, 0)
		elif et == 0x8:
			if not tick:
				self.pan = ep
		elif et == 0x9:
			if self.playsmp and not tick:
				self.baseoffs = self.offs = ep<<8
				if self.offs > self.playsmp.length-2:
					self.offs = self.playsmp.length-2
				self.suboffs = 0
		elif et == 0xA:
			self.eff_slide_vol(tick, eph, epl)
		elif et == 0xB:
			if not tick:
				if not self.parent.hasbumped:
					self.parent.currow = 0
				self.parent.setord(ep)
				self.parent.hasbumped = True
		elif et == 0xC:
			if not tick:
				self.tvol = self.vol = ep
		elif et == 0xD:
			if not tick:
				if not self.parent.hasbumped:
					self.parent.setord(self.parent.curord+1)
				self.parent.currow = eph*10+epl
				self.parent.hasbumped = True
		elif et == 0xF:
			if not tick:
				if ep >= 0x20:
					self.parent.bpm = ep
				elif ep:
					self.parent.tpr = ep
		
		if self.eff_ivlspeed:
			self.eff_ivlpos += self.eff_ivlspeed
			if self.eff_ivlpos & 0x80:
				if self.eff_ivlwpos > self.latchsmp.lplen:
					self.eff_ivlwpos = 0
				self.eff_ivlpos = 0
				self.latchsmp.funkit(self.eff_ivlwpos)
				self.eff_ivlwpos += 1
	
	def mix(self, arr, dspspeed):
		if self.playsmp and self.offs != -1:
			z = int(AMICLK/self.tperiod)
			r = dspspeed
			v = self.tvol
			o = self.offs
			s = self.suboffs
			d = self.playsmp.data
			if self.eff_ivlon:
				d = self.playsmp.idata
			q = d[o]*v
			
			ff = z*v/256
			if ff < 0.01:
				ff = 0.01
			fv = dspspeed/(2.0*math.pi*ff)
			if fv <= 1.0:
				fv = 1.0
				#print "FILTER CLAMP!"
			cfv = 1.0/(fv**2)
			s2 = v/256.0
			if s2 < 0.04:
				s2 = 0.04
			s1 = cfv/s2
			q1 = self.q1
			q2 = self.q2
			try:
				if STEREO:
					t = u = 0x80
					if self.pan < 0x80:
						u = self.pan
					else:
						t = 0xFF-self.pan
					
					b = (q*t)>>7
					c = (q*u)>>7
					
					for i in xrange(0,len(arr),2):
						q2 += (q-q1-q2)*s2
						q1 += q2*s1
						iq = int(q1)
						b = (iq*t)>>7
						c = (iq*u)>>7
						
						arr[i] += b
						arr[i+1] += c
						
						s += z
						if s > r:
							o += s/r
							s %= r
							q = d[o]*v
				else:
					for i in xrange(len(arr)):
						q2 += (q-q1-q2)*s2
						q1 += q2*s1
						
						arr[i] += int(q1)
						
						s += z
						if s > r:
							o += s/r
							s %= r
							q = d[o]*v
			except IndexError:
				print "NOTE OVERSHOT - *NOT* A VALID MOD!"
			
			self.q1 = q1
			self.q2 = q2
			
			if o >= self.playsmp.length+self.playsmp.lplen:
				if self.playsmp.lplen:
					o = (o - self.playsmp.length) % self.playsmp.lplen + self.playsmp.length
				else:
					s = o = -1
					#self.playsmp = None
			self.offs = o
			self.suboffs = s
		

class ModPlayer:
	def __init__(self, fname):
		fp = open(fname, "rb")
		self.gettaginfo(fp)
		fp.seek(0)
		self.name = fp.read(20).replace("\x00"," ")
		for i in xrange(32):
			self.name = self.name.replace(chr(i),"*")
		print "Module name: " + self.name
		print "Samples:"
		self.smplist = []
		for i in xrange(self.smpcount):
			self.smplist.append(ModSample(fp))
			print "  %02i - %s" % (i+1, self.smplist[-1].name)
		self.ordlistlen = u8be(fp)
		self.respos = u8be(fp)
		self.ordlist = [u8be(fp) for i in xrange(128)]
		self.patcount = 0
		for o in self.ordlist:
			if self.patcount < o:
				self.patcount = o
		self.patcount += 1
		print "Patterns: %i" % self.patcount
		print "Orders: %i" % self.ordlistlen
		
		self.chncount = 4
		self.flt8 = False
		
		# OK, be warned, there's a LOT of detection going on.
		# One of these types are REALLY, REALLY rare
		# (I've only ever seen it in one module,
		#  and haven't found the tracker in question).
		if self.chnname == None:
			if self.respos == 0x78:
				print "Format: 15-sample SoundTracker"
			else:
				print "Format: 15-sample unknown"
		elif self.chnname == "M.K." or self.chnname == "M!K!":
			if self.chnname == "M.K.":
				if self.respos == 0x7F:
					print "Format: 4-channel ProTracker / ScreamTracker 3"
				elif self.respos == 0x78:
					print "Format: 4-channel unknown ($78)"
				else:
					print "Format: 4-channel NoiseTracker / FastTracker"
			elif self.respos == 0x7F:
				print "Format: 4-channel ProTracker"
			elif self.respos == 0x78:
				print "Format: 4-channel unknown (M!K! $78)"
			else:
				print "Format: 4-channel FastTracker"
		elif self.chnname == "FLT4":
			if self.respos == 0x7F:
				print "Format: 4-channel unknown (FLT4 $7F)"
			elif self.respos == 0x78:
				print "Format: 4-channel unknown (FLT4 $78)"
			else:
				print "Format: 4-channel StarTrekker"
		elif self.chnname == "FLT8":
			self.chncount = 8
			self.flt8 = True
			if self.respos == 0x7F:
				print "Format: 8-channel-fairlight unknown ($7F)"
			elif self.respos == 0x78:
				print "Format: 8-channel-fairlight unknown ($78)"
			else:
				print "Format: 8-channel-fairlight StarTrekker"
		elif self.chnname == "M&K!":
			# only found in echobea3.mod.
			# hardly anything plays this bugger.
			print "Format: Fleg's Module Train-er (unreleased?)"
		elif self.chnname == "6CHN":
			self.chncount = 6
			if self.respos == 0x7F:
				print "Format: 6-channel ScreamTracker 3"
			elif self.respos == 0x78:
				print "Format: 6-channel unknown ($78)"
			else:
				print "Format: 6-channel FastTracker"
		elif self.chnname == "8CHN":
			self.chncount = 8
			if self.respos == 0x7F:
				print "Format: 8-channel ScreamTracker 3"
			elif self.respos == 0x78:
				print "Format: 8-channel unknown ($78)"
			else:
				print "Format: 8-channel FastTracker"
		elif self.chnname == "OCTA":
			self.chncount = 8
			print "Format: %i-channel OctaMED(?) ($%02X)" % (self.chncount, self.respos)
		elif self.chnname == "OKTA" or self.chnname == "CD81":
			self.chncount = 8
			print "Format: %i-channel Oktalyzer ($%02X)" % (self.chncount, self.respos)
		elif self.chnname == "TDZ1" or self.chnname == "TDZ2" or self.chnname == "TDZ3":
			self.chncount = ord(self.chnname[3]) - 0x30
			print "Format: %i-channel TakeTracker ($%02X)" % (self.chncount, self.respos)
		elif self.chnname[1:] == "CHN" and ord(self.chnname[0]) >= 0x31 and ord(self.chnname[0]) <= 0x39:
			self.chncount = ord(self.chnname[0]) - 0x30
			if self.chncount >= 5:
				print "Format: %i-channel TakeTracker ($%02X)" % (self.chncount, self.respos)
			elif self.chncount == 2:
				if self.respos == 0x7F:
					print "Format: %i-channel unknown ($7F)" % self.chncount
				elif self.respos == 0x78:
					print "Format: %i-channel unknown ($78)" % self.chncount
				else:
					print "Format: %i-channel FastTracker" % self.chncount
			else:
				print "Format: %i-channel unknown ($%02X)" % (self.chncount, self.respos)
		elif self.chnname[2:] == "CH":
			self.chncount = ord(self.chnname[0]) - 0x30
			self.chncount *= 10
			self.chncount += ord(self.chnname[1]) - 0x30
			
			if (self.chncount & 1) == 0 and self.chncount <= 32:
				if self.respos == 0x7F:
					print "Format: %i-channel unknown (CH $7F)" % self.chncount
				elif self.respos == 0x78:
					print "Format: %i-channel unknown (CH $78)" % self.chncount
				else:
					print "Format: %i-channel FastTracker" % self.chncount
			else:
				print "Format: %i-channel unknown (CH $%02X)" % (self.chncount, self.respos)
		elif self.chnname[2:] == "CN":
			self.chncount = ord(self.chnname[0]) - 0x30
			self.chncount *= 10
			self.chncount += ord(self.chnname[1]) - 0x30
			
			print "Format: %i-channel TakeTracker (CN $%02X)" % (self.chncount, self.respos)
		else:
			print "Format: unknown ("+self.chnname+")"
		
		if self.respos == 0x7F or self.respos == 0x78:
			self.respos = 0x00
		else:
			self.respos &= 0x7F
		
		while len(self.ordlist) < 257:
			self.ordlist.append(-1)
		
		for i in xrange(self.ordlistlen, 257):
			self.ordlist[i] = -1
		
		if self.smpcount == 31:
			print "Read check: [%s]" % fp.read(4)
		
		if self.flt8: # always has an odd number of virtual patterns
			self.patcount += 1
		
		print "Loading %i patterns" % self.patcount
		self.patlist = []
		for i in xrange(self.patcount):
			self.patlist.append(ModPattern(fp, self.chncount, self.flt8))
			if self.flt8 and i > 0:
				self.patlist[-2].flt8merge(self.patlist[-1])
		
		print "Loading %i sample waveforms" % self.smpcount
		for i in xrange(self.smpcount):
			self.smplist[i].loadwf(fp)
		
		fp.close()
		
		self.mixoffs = 0
		self.fpos1 = [128]*(2 if STEREO else 1)
		self.fpos2 = [0]*(2 if STEREO else 1)
		self.filteron = False
		
		self.filtersweep = 0
		
		self.bpm = 125
		self.tpr = 6
		self.setord(0)
		self.currow_real = self.currow = 0
		self.curpat_real = self.curpat
		self.curord_real = self.curord
		self.curtick = 0
		
		self.chnlist = [ModChannel(self,0x40 if (not (i&1)) == (not (i&2)) else 0xBF) for i in xrange(self.chncount)]
	
	def setord(self, o):
		self.curord = o
		self.curpat = self.ordlist[o]
		if self.curpat == -1:
			if o != self.respos:
				self.setord(self.respos)
			else:
				self.curpat = 0
	
	def dotick(self, dsp, dspspeed):
		#time.sleep(0.02)
		q = self.patlist[self.curpat].data[max(0,self.currow)]
		if not self.curtick:
			self.hasbumped = False
			
			s = ""
			buflen = dspspeed
			for i in xrange(self.chncount):
				k = q[i]
				self.chnlist[i].set_stuff(k)
				
				if DISPLAYISHTHINGY:
					s += "%03X%02X%X%02X|" % (k.period, k.smp, k.efftype, k.effparam)
			
			if DISPLAYISHTHINGY:
				print s
		
		arr = [32768 for i in xrange(((dspspeed*10)/(4*self.bpm))*(2 if STEREO else 1))]
		for chn in self.chnlist:
			chn.tick_stuff(self.curtick)
		for chn in self.chnlist:
			chn.mix(arr, dspspeed)
		
		m = self.mixoffs
		v = 0
		
		
		# this kinda cheats wrt stereo
		pi2 = 3.14159265358979*2
		f = dspspeed/10
		z = 0
		g = dspspeed*2
		
		fsi = 3.14159265358979*2/(dspspeed*10.0)
		for zch in xrange(2 if STEREO else 1):
			fs = self.filtersweep
			
			d1 = self.fpos1[zch]
			d2 = self.fpos2[zch]
			for i in xrange(zch,len(arr),(2 if STEREO else 1)):
				p = arr[i]*2-m
				if p < 0:
					v = p
					p = 0
				elif p > 65535:
					v = (p-65535)
					p = 65535
				else:
					v = 0
				m += v
				
				fs += fsi
				
				#pz = p-d1
				#d3 = pz-d2
				#d2 += (d3*f)/dspspeed
				#d1 += (d2*g)/dspspeed
				#q = d1/256
				q = p/256
				if q < 0:
					q = 0
				elif q > 255:
					q = 255
				
				arr[i] = q
			
			self.fpos1[zch] = d1
			self.fpos2[zch] = d2
		
		self.filtersweep = fs
		
		self.mixoffs = m
		
		if dsp:
			dsp.writeall(''.join(chr(c) for c in arr))
		else:
			play_wincrap(arr, dspspeed)
		
		self.curtick += 1
		if self.curtick >= self.tpr:
			if not self.hasbumped:
				self.currow += 1
			# HAPPY FUN TEST for E0x filter
			# based on A1200 filter
			if HAPPYFUNTEST and self.currow == 30:
				self.filteron = not self.filteron
			if self.currow >= 64 or self.hasbumped:
				if DISPLAYISHTHINGY:
					s = ""
					for i in xrange(self.chncount):
						s += "--------+"
					print s
				if self.currow >= 64 or self.curord != self.curord_real:
					for i in xrange(self.chncount):
						# according to MikMod, this is a quirk.
						self.chnlist[i].eff_lbkpos = -1
			if self.currow >= 64:
				self.currow = 0
				self.setord(self.curord+1)
			self.curtick = 0
			self.currow_real = self.currow
			self.curpat_real = self.curpat
			self.curord_real = self.curord
	
	def gettaginfo(self, fp):
		fp.seek(1080)
		self.chnname = fp.read(4)
		for c in self.chnname:
			if ord(c) < 32 or ord(c) > 126:
				self.chnname = None
				self.smpcount = 15
				return
		
		self.smpcount = 31

mod = ModPlayer(sys.argv[1])

# don't pass /dev/dsp, let it autodetect
# this is for systems like NetBSD where the device is /dev/audio
dspspeed = 32000
if ossaudiodev:
	dsp = ossaudiodev.open("w")
	if dsp.setfmt(ossaudiodev.AFMT_U8) != ossaudiodev.AFMT_U8:
		print "ERROR: Could not set audio format to unsigned 8."
		dsp.close()
		sys.exit()
	dspspeed = dsp.speed(dspspeed)
	STEREO = dsp.channels(2 if STEREO else 1) == 2
else:
	dsp = None

print "Speed: %ihz" % dspspeed

try:
	while True:
		mod.dotick(dsp, dspspeed)
except KeyboardInterrupt:
	print "boom ok let's close this thing now"

if dsp:
	dsp.close()
else:
	print "closing"
	wincrapobj.shutup = True
	print "should be silent in a few secs"
