#!/usr/bin/env python --
# -*- coding: utf-8 -*-
#
# IT2TIA converter by Ben "GreaseMonkey" Russell, 2011 -- PUBLIC DOMAIN
# You will need the IT2TIA driver (sunds.bin).
# 
# Some requirements:
# - Full channel volumes, tempo 150.
# - Mono, samples, compat Gxx off, old effects off, Amiga slides.
# - Bxx on last pattern played.
# - If it's not an effect, don't put it past the second channel.
# - Same goes for effects that affect pitch/volume/waveform.
#
# Notes:
# - YOU MUST EXPLICITLY USE Bxx TO LOOP BACK.
# - Cxx should only be C00 and NOT in any other form.
# - Txx WILL NOT WORK. TEMPO MUST BE 150.
# - Same for Pxy, Xxx, Yxy (no panning).
# - Same for Mxx, Nxy, Vxx (no multiplies, so no chvol/glbvol).
# - Same for Oxx, Zxx, SAx (no sample modification).
# - Same for S3x, S4x, S5x (triangle mod only - also S5x == panning).
# - Same for SBx (ruins linearity + this converter won't like you).
# - Some stuff has not been implemented yet. Check this script.
# - There are no voleffects other than "set volume" at this stage.
# - Each pattern MUST HAVE THE SAME SPEED INFO EACH TIME AROUND.
# - Don't use separators (+++) in your orderlist, it's STUPID and IT'LL BREAK.
# - PATTERNS WILL PLAY THE SAME WAY EACH TIME AROUND.
#   If you want anything playing at a different speed or something,
#   copy/paste into a new pattern.
#   By the way, playback ordering pertains to the orderlist.
# - Don't put too much on the last tick of a pattern.
#   This is a converter limitation. YOU WILL LEAK EXTRA TICKS INTO THE PATTERN.
#   In fact, it's best not to put too much on ANY tick.
#
# Space specific notes:
# - Orders + (Patterns * 2) <= 256.
# - Patterns cannot change info more than 256 times.
#   You may need smaller patterns.
# - Try not to use vibrato (Hxy) too much. (NOT IMPLEMENTED YET)
# - Avoid using Jxy ESPECIALLY. (NOT IMPLEMENTED YET)
# - Unused patterns will be ignored.

import sys,struct

TIACLK = 31440
if len(sys.argv) <= 1:
	print "generating pack..."
	
	AMICLK = 14317056/4 # from ST3 clock
	BIGGESTPERIOD = 256
	# Lowest note: A-3 @ 1016/4
	LOWESTNOTE = 1016/4
	ITBOTTOM = 13.375
	SMPDATAMUL = int(LOWESTNOTE/ITBOTTOM+0.5)
	SMPFRQ = int(AMICLK/ITBOTTOM*2.0+0.5)
	
	#SMPNOTES = []
	
	def dotaps(cyclen,bits,taps,r=True,bv=0):
		v = 0
		l = []
		for i in xrange(cyclen+bits*2):
			q = bv & taps
			# SIMD FTW
			q = (q>>8)^q
			q = (q>>4)^q
			q = (q>>2)^q
			q = ((q>>1)^q)&1
			l.append(120 if (bv&1) else -120)
			if (not q) == (not r):
				bv >>= 1
			else:
				bv = (bv>>1)|(1<<(bits-1))
		return l[bits*2:]
	
	def mergetapsand(params1,params2):
		l1 = dotaps(*params1)
		l2 = dotaps(*params2)
		
		return [l1[i] if l2[i] > 0 else l2[i] for i in xrange(len(l1))]
	
	def mergetapsor(params1,params2):
		l1 = dotaps(*params1)
		l2 = dotaps(*params2)
		
		return [l1[i] if l1[i] > 0 else l2[i] for i in xrange(len(l1))]
	
	def dosquare(ones,zeros):
		return [120]*ones + [-120]*zeros
	
	def triple(l):
		tl = []
		for v in l:
			tl.append(v)
			tl.append(v)
			tl.append(v)
		return tl
	
	SAMPLEDATA = [
		dotaps(4,4,0b0000), # 0
		dotaps(15,4,0b0011), # 1
		mergetapsand((465,4,0b0011),(465,5,0b00011,False,0x10)), # 2
		mergetapsor((465,4,0b0011),(465,5,0b00011,False,0x10)), # 3
		dosquare(1,1)+dosquare(1,1), # 4
		dosquare(1,1)+dosquare(1,1), # 5
		dosquare(13,18), # 6
		dotaps(31,5,0b00011,False,0x10), # 7
		dotaps(511,9,0b000010001,False,0x100), # 8
		dotaps(31,5,0b00011,False,0x10), # 9
		dosquare(13,18), # 10
		dotaps(4,4,0b0000), # 11
		triple(dosquare(1,1)), # 12
		triple(dosquare(1,1)), # 13
		triple(dosquare(13,18)), # 14
		triple(dotaps(31,5,0b00011,False,0x10)), # 15
	]
	
	smpasc = []
	v = 0
	for d in SAMPLEDATA:
		smpasc.append(v*SMPDATAMUL)
		v += len(d)
	
	print len(SAMPLEDATA)
	
	fp = open("tiapack.it","wb")
	fp.write("IMPM")
	fp.write("it2tia pack              \x00")
	fp.write(struct.pack("<HHHHH",0x1004,2,0,len(SAMPLEDATA),0))
	fp.write(struct.pack("<HHHH",0x0216,0x0200,0x0000,0x0000))
	fp.write(struct.pack("<BBBBBBHII",128,48,6,150,128,0,0,0,0xCEFA77B0))
	fp.write(chr(32)*64)
	fp.write(chr(64)*64)
	fp.write(chr(255)*2)
	smpheads = fp.tell()+4*len(SAMPLEDATA)+2
	smpdatas = smpheads+0x50*len(SAMPLEDATA)
	
	for i in xrange(len(SAMPLEDATA)):
		fp.write(struct.pack("<I",smpheads+i*0x50))
	fp.write(chr(0)*2)
	
	for i in xrange(len(SAMPLEDATA)):
		smp = SAMPLEDATA[i]
		fp.write("IMPSit2tiapy.smp\x00")
		fp.write(struct.pack("<BBB",64,0x11,64))
		fp.write("Waveform %02i              \x00" % i)
		fp.write(struct.pack("<BBIIIIIIIBBBB"
			,0x01,0x00
			,len(smp)*SMPDATAMUL,0,len(smp)*SMPDATAMUL
			,SMPFRQ,0,0,smpasc[i]+smpdatas
			,0,0,0,0))
	
	for i in xrange(len(SAMPLEDATA)):
		for v in SAMPLEDATA[i]:
			fp.write(chr(255&v)*SMPDATAMUL)
	
	fp.close()
	
	exit()
###############################################
#                                             #
#            ACTUAL RENDITION CODE            #
#                                             #
###############################################

CH01 = "ABCDEFGHIJKLQRS"
CH01S = [3,4,5,6,8,0xB,0xC,0xD,0xE]
CANBEZERO = "BC"
IGNOREPARAM = "C"
PTAB = [int(v*0x100/1712.0+0.5) for v in [1712,1616,1524,1440,1356,1280,1208,1140,1076,1016,960,907]]
CDTAB = [0xF8*(i+1)/32 for i in xrange(32)][::-1]
print CDTAB
XPTAB = []
for i in xrange(120):
	expper = PTAB[i%12]>>(i//12)
	actper = expper >> 3
	if actper == 0:
		XPTAB.append(0)
	else:
		frqh = TIACLK/actper
		frqm = TIACLK*8/expper
		if actper > 1:
			frql = TIACLK/(actper+1)
		else:
			XPTAB.append(0)
			continue
		print i,frql,frqm,frqh
		XPTAB.append(actper*8-8+((frqh-frqm)*16+1)/(2*(frqh-frql)))
	
print XPTAB
# LOAD .it file
fp = open(sys.argv[1],"rb")
if fp.read(4) != "IMPM":
	raise Exception("not an IMPM module")
fp.read(26) # skip name
fp.read(2) # skip pat highlight
ordnum, insnum, smpnum, patnum, cwt, cmwt, itflags, itspecial = struct.unpack("<HHHHHHHH",fp.read(16))
gvol,mvol,speed,tempo,pansep,pwd,msglen,msgoffs,timestamp = struct.unpack("<BBBBBBHII",fp.read(16))
fp.read(64) # skip channel panning
fp.read(64) # skip channel volume
ordlist = [ord(v) for v in fp.read(ordnum)]
fp.read((insnum+smpnum)*4) # skip instruments / samples
patptrlist = [struct.unpack("<I",fp.read(4))[0] for i in xrange(patnum)]

while ordlist[-1] == 255:
	ordlist = ordlist[:-1]
	ordnum -= 1

patsused = []
for patidx in ordlist:
	if not (patidx in patsused):
		patsused.append(patidx)

patptrlist = [patptrlist[patidx] for patidx in patsused]
ordlist = [patsused.index(patidx) for patidx in ordlist]
patnum = len(patptrlist)
patdatalist = [None for i in xrange(patnum)]

bytesfreeinheader = 256-(ordnum+patnum*2)
print "%i orders, %i patterns, %i bytes free in header" % (ordnum,patnum,bytesfreeinheader)
if bytesfreeinheader < 0:
	raise Exception("Out of orderlist/patternpointerlist space")
print "Patterns used:", patsused
print "New orderlist:", ordlist
print ".it pattern pointers:", patptrlist

# Read pattern data
for order in ordlist:
	if patdatalist[order] == None:
		print "Pattern %i (was %i) - NEW DATA" % (order, patsused[order])
	else:
		print "Pattern %i (was %i) - passing through for info" % (order, patsused[order])

	data = [[]]
	lmask = [0 for i in xrange(64)]
	lnote = [-1 for i in xrange(64)]
	lsmp = [0 for i in xrange(64)]
	lvol = [-1 for i in xrange(64)]
	left = [0 for i in xrange(64)]
	lefp = [0 for i in xrange(64)]
	lnzefp = [0 for i in xrange(64)]
	
	pnote = [-1 for i in xrange(2)]
	psmp = [-1 for i in xrange(2)]
	pvol = [-1 for i in xrange(2)]
	ppes = [0 for i in xrange(2)]
	pvos = [0 for i in xrange(2)]
	
	cnote = [-1 for i in xrange(2)]
	csmp = [-1 for i in xrange(2)]
	cvol = [-1 for i in xrange(2)]
	cpes = [0 for i in xrange(2)]
	cvos = [0 for i in xrange(2)]
	
	fp.seek(patptrlist[order])
	_, rows, _ = struct.unpack("<HHI",fp.read(8)) # ignore length / reserved dword
	no_more_rows = False
	for r in xrange(rows):
		if no_more_rows:
			break
		
		while True:
			ch = ord(fp.read(1))
			if ch == 0:
				break
			elif ch & 0x80:
				ch -= 0x81
				lmask[ch] = ord(fp.read(1))
			else:
				ch -= 1
			
			if lmask[ch] & 0x01:
				lnote[ch] = ord(fp.read(1))
			if lmask[ch] & 0x02:
				lsmp[ch] = ord(fp.read(1))
			if lmask[ch] & 0x04:
				lvol[ch] = ord(fp.read(1))
			if lmask[ch] & 0x08:
				left[ch] = ord(fp.read(1))
				lefp[ch] = ord(fp.read(1))
				if lefp[ch] != 0x00:
					lnzefp[ch] = lefp[ch]
			
			if lmask[ch] & 0x88:
				# TODO effects
				pass
			if lmask[ch] & 0x22:
				if lsmp[ch] != 0:
					csmp[ch] = lsmp[ch]-1
					cvol[ch] = 63
			if lmask[ch] & 0x44:
				cvol[ch] = min(lvol[ch],63)
			if lmask[ch] & 0x11:
				note = lnote[ch]
				if note == 254:
					cvol[ch] = 0 # The easy way.
				elif note <= 119:
					#cnote[ch] = (PTAB[note%12]>>(note/12))-0x8
					cnote[ch] = XPTAB[note]
					#print "n%02X=%02X" % (ch,cnote[ch])
					#cnote[ch] = int(0xF8*(2.0**((-1-note)/12.0)))
		
		curtick = 0
		while curtick < speed:
			# TODO effects
			
			for ch in xrange(64):
				if lmask[ch] & 0x88:
					eft = left[ch]
					efp = lefp[ch]
					if eft == 2:
						if not curtick:
							print "ORDER JUMP"
							data[-1].append((0xB0,efp))
							no_more_rows = True
					elif eft == 3:
						if not curtick:
							print "Cxx EFFECT"
							no_more_rows = True
			
			# TODO: do spillover tests on the fly
			for ch in xrange(2):
				if cnote[ch] != pnote[ch]:
					data[-1].append((0x86+ch,cnote[ch]))
				if csmp[ch] != psmp[ch]:
					data[-1].append((0x15+ch,csmp[ch]))
				if cvol[ch] != pvol[ch]:
					data[-1].append((0x84+ch,cvol[ch]))
				if cpes[ch] != ppes[ch]:
					data[-1].append((0x88+ch,cpes[ch]))
				if cvos[ch] != pvos[ch]:
					data[-1].append((0x8A+ch,cvos[ch]))
				
				cnote[ch] = (cnote[ch]+cpes[ch])&255
				cvol[ch] = (cvos[ch]+cvol[ch])&255
				
				pnote[ch] = cnote[ch]
				psmp[ch] = csmp[ch]
				pvol[ch] = cvol[ch]
				ppes[ch] = cpes[ch]
				pvos[ch] = cvos[ch]
			
			curtick += 1
			data.append([])
	
	if patdatalist[order] == None:
		patdatalist[order] = data[:-1]
		#print data

# Close .it
fp.close()

# Open .bin + copy driver data
bin = open(sys.argv[2],"w+b")
srcbin = open("sunds.bin","rb")
bin.write(srcbin.read())
srcbin.close()
bin.seek(256)
freeptr, = struct.unpack("<H", bin.read(2))
print "%i bytes free space in driver" % (0xFFFC-freeptr)
freeptr -= 0xF000
patbinptrs = []
print "freeptr: %04X" % freeptr
bin.seek(freeptr)

# Actually write data
# TODO
for i in xrange(patnum):
	q = bin.tell()
	if (q&0xFF) > 0x100-8:
		bin.seek((q&0xFF00)+0x100)
		q = bin.tell()
	q += 0xF000
	print "Pattern %02X @ %04X" % (i*2+ordnum, q)
	patbinptrs.append(q)
	data = patdatalist[i][:]
	datq = []
	awaitlength = -1
	curlength = 0
	za = bin.tell()
	while data or datq:
		if data:
			datq += data.pop(0)
		else:
			print "* PATTERN LEAKED A TICK *"
		
		if datq:
			curlength += 1
			if curlength > 256:
				raise Exception("pattern too complex - split it")
			bin.write(chr(awaitlength&0xFF))
			
			q = bin.tell()
			# XXX: THIS JUST LOOKS LIKE IT'LL BREAK.
			reslast = ((q&0xFF) > 0x100-7-7 and (q&0xFF) != 0x100-7)
			
			zq = []
			for i in xrange(2 if reslast else 3):
				if datq:
					zq.append(datq.pop(0))
				else:
					zq.append((0x80,0x00))
			
			a,b = zq.pop(0)
			bin.write(chr(a)+chr(b))
			a,b = zq.pop(0)
			bin.write(chr(a)+chr(b))
			
			if reslast:
				print "page crossing"
				a,b = 0xB2,0xFF-6
				bin.write(chr(a)+chr(b))
				while (bin.tell()&0xFF) != 0xFF:
					bin.write("\x00")
			else:
				a,b = zq.pop(0)
				bin.write(chr(a)+chr(b))
			
			awaitlength = 1
		else:
			awaitlength += 1
			if awaitlength == 256:
				print "BUGBUGBUG: fix the case where \"row\" length >= 256"
				print "prod GreaseMonkey about it"
				raise Exception()
	
	if awaitlength >= 1:
		bin.write(chr(awaitlength))
	
	zz = bin.tell()
	bin.seek(za)
	bin.write(chr(curlength))
	bin.seek(zz)

# Write order/pattern table
bin.seek(0)
bin.write(''.join(chr(v*2+ordnum) for v in ordlist))
for v in patbinptrs:
	bin.write(struct.pack("<H",v))

# Close new .bin
bin.close()
