import sys, struct

def nulstrip(s):
	if "\x00" in s:
		s, _, _ = s.partition("\x00")
	return s

efx_remap_exx = {
	0x0: lambda p,h,l : ('@', 0), # not in MTM
	0x1: lambda p,h,l : ('F', 0xF0+l) if l != 0 else ('@', 0),
	0x2: lambda p,h,l : ('E', 0xF0+l) if l != 0 else ('@', 0),
	0x3: lambda p,h,l : ('@', 0), # not in MTM
	0x4: lambda p,h,l : ('@', 0), # not in MTM
	0x5: lambda p,h,l : ('S', 0x20+l), # not in IT, deprecated in MTM
	0x6: lambda p,h,l : ('@', 0), # not in MTM
	0x7: lambda p,h,l : ('@', 0), # not in MTM
	0x8: lambda p,h,l : ('S', 0x80+l),
	0x9: lambda p,h,l : ('Q', l) if l != 0 else ('@', 0),
	0xA: lambda p,h,l : ('D', 0x0F+l*16),
	0xB: lambda p,h,l : ('D', 0xF0+l),
	0xC: lambda p,h,l : ('S', 0xC0+l),
	0xD: lambda p,h,l : ('S', 0xD0+l),
	0xE: lambda p,h,l : ('S', 0x60+l),
	0xF: lambda p,h,l : ('@', 0), # not in MTM
}

efx_remap = {
	0x0: lambda p,h,l : ('J', p) if p != 0 else ('@', 0),
	0x1: lambda p,h,l : ('F', min(0xDF,p)) if (h==0) != (l==0) else ('@', 0),
	0x2: lambda p,h,l : ('E', min(0xDF,p)) if (h==0) != (l==0) else ('@', 0),
	0x3: lambda p,h,l : ('G', p),
	0x4: lambda p,h,l : ('H', p),
	0x5: lambda p,h,l : ('L', p) if (h==0) != (l==0) else ('G', 0),
	0x6: lambda p,h,l : ('K', p) if (h==0) != (l==0) else ('H', 0),
	0x7: lambda p,h,l : ('R', p),
	0x8: lambda p,h,l : ('@', 0), # not in MTM, use E8x instead
	0x9: lambda p,h,l : ('O', p) if (h==0) != (l==0) else ('@', 0),
	0xA: lambda p,h,l : ('D', p) if (h==0) != (l==0) else ('@', 0),
	0xB: lambda p,h,l : ('B', p),
	0xC: lambda p,h,l : ('*', p),
	0xD: lambda p,h,l : ('C', p),
	0xE: lambda p,h,l : efx_remap_exx[h](p,h,l),
	0xF: lambda p,h,l : ('A' if p < 32 else 'T', p),
}

infp = open(sys.argv[1],"rb")
if infp.read(3) != "MTM":
	raise Exception("not an MTM file")
version = ord(infp.read(1))
print "version",hex(version)
songname = infp.read(20)+"\x00"*6
print repr(nulstrip(songname))
trknum, patnum, ordnum = struct.unpack("<HBB", infp.read(4))
patnum += 1
ordnum += 1
print trknum, patnum, ordnum
msglen, smpnum, attrbyte = struct.unpack("<HBB", infp.read(4))
print msglen, smpnum, attrbyte
trklen, chnnum = struct.unpack("<BB", infp.read(2))
print trklen, chnnum

chnpan = [ord(v)*4+2 for v in infp.read(32)]
print chnpan

smplist = []
for i in xrange(smpnum):
	smp = {}
	smp['name'] = infp.read(22)+"\x00"*4
	smp['len'], smp['lpbeg'], smp['lpend'] = struct.unpack(
		"<III", infp.read(12))
	smp['ft'], smp['vol'], smp['attr'] = struct.unpack(
		"<BBB", infp.read(3))
	print i+1, smp
	smplist.append(smp)

ordlist = [ord(v) for v in infp.read(128)]
print ordlist

trklist = [[(False, None) for i in xrange(64)]]
for i in xrange(trknum):
	l = []
	lmask = 0x00
	lnote = 253
	lins = 0
	lvol = 255
	left = 0
	lefp = 0
	for j in xrange(64):
		# load 3-byte BE value
		b1,b2,b3 = struct.unpack("<BBB", infp.read(3))
		bx = (b1<<16)+(b2<<8)+b3
		
		# extract data
		note = (bx>>18)&63
		ins = (bx>>12)&63
		eft = (bx>>8)&15
		efp = bx&255
		
		# convert to IT
		note = 253 if note == 0 else (60-12*2)+note
		eh = efp>>4
		el = efp&15
		eft, efp = efx_remap[eft](efp,eh,el)
		vol = 255
		
		if eft == '*':
			vol = efp
			eft = 0
			efp = 0
		else:
			eft = ord(eft)-0x40
		
		# calculate mask
		mask = 0
		if note != 253:
			mask |= 0x10 if note == lnote else 0x01
			lnote = note
		if ins != 0:
			mask |= 0x20 if ins == lins else 0x02
			lins = ins
		if vol != 255:
			mask |= 0x40 if vol == lvol else 0x04
			lvol = vol
		if eft != 0 and efp != 0:
			mask |= 0x80 if eft==left and efp==lefp else 0x08
			left = eft
			lefp = efp
		
		# pack it
		xl = []
		if mask != lmask:
			xl.append(mask)
		
		if mask & 0x01:
			xl.append(lnote)
		if mask & 0x02:
			xl.append(lins)
		if mask & 0x04:
			xl.append(lvol)
		if mask & 0x08:
			xl.append(left)
			xl.append(lefp)
		
		# stash it
		if mask != 0:
			l.append(((mask != lmask), xl))
			lmask = mask
		else:
			l.append((False, None))
	
	trklist.append(l)

patlist = []
for i in xrange(patnum):
	l = [struct.unpack("<H",infp.read(2))[0] for j in xrange(32)]
	patlist.append(l)

msgdata = ""
msgbase = infp.read(msglen)
while msgbase != "":
	m = msgbase[:40]
	msgbase = msgbase[40:]
	while m.endswith("\x00"):
		m = m[:-1]
	m = m.replace("\x00"," ")
	msgdata += m+"\r"
msgdata += "\x00"

print repr(msgdata)

for i in xrange(smpnum):
	smp = smplist[i]
	smplen = smp['len']
	smpattr = smp['attr']
	if smpattr & 1: # 16-bit sample
		smplen *= 2
	print smplen
	smp['data'] = infp.read(smplen)

print infp.tell()

infp.close()

outfp = open(sys.argv[2],"wb")

outfp.write("IMPM" + songname + "\x04\x10")
outfp.write(struct.pack("<HHHH", ordnum+1, 0, smpnum, patnum))
outfp.write(struct.pack("<HHHH", 0xE7E0, 0x0200, 0x31, 0x0001))
outfp.write(struct.pack("<BBBBBBH", 128,48,6,125,128,0,len(msgdata)))
msgoffs = outfp.tell()
outfp.write("oopsMTM"+chr(version))
outfp.write(''.join(chr(v) for v in chnpan))
outfp.write("\xA0"*32)
outfp.write("\x40"*64)
outfp.write(''.join(chr(ordlist[i]) for i in xrange(ordnum)))
outfp.write("\xFF")
smpoffs = outfp.tell()
outfp.write("oopS"*smpnum)
patoffs = outfp.tell()
outfp.write("ooPs"*patnum)
outfp.write("\x00"*6)
t = outfp.tell()
outfp.seek(msgoffs)
outfp.write(struct.pack("<I", t))
outfp.seek(t)
outfp.write(msgdata)

for i in xrange(smpnum):
	t = outfp.tell()
	outfp.seek(smpoffs)
	outfp.write(struct.pack("<I", t))
	smpoffs += 4
	outfp.seek(t)
	
	smp = smplist[i]
	outfp.write("IMPS" + "mtm2itPY.wav" + "\x00")
	flg = 0x01
	if smp['lpend'] != 0:
		flg |= 0x10
	if smp['attr'] & 0x01:
		flg |= 0x02
	
	ft = smp['ft']
	freq = 8363
	# TODO: handle finetune!
	#print ft
	
	outfp.write(struct.pack("<BBB",64,flg,vol))
	outfp.write(smp['name'])
	outfp.write(struct.pack("<BB",0x01,0x20))
	outfp.write(struct.pack("<I",smp['len']))
	outfp.write(struct.pack("<I",smp['lpbeg']))
	outfp.write(struct.pack("<I",smp['lpend']))
	outfp.write(struct.pack("<III",freq,0,0))
	outfp.write(struct.pack("<I",outfp.tell()+8))
	outfp.write(struct.pack("<BBBB",0,0,0,0))
	data = smp['data']
	if flg & 0x02:
		pass # TODO: 16-bit conversion?
	else:
		data = ''.join(chr(ord(v)^0x80) for v in data)
	outfp.write(data)

for i in xrange(patnum):
	t = outfp.tell()
	outfp.seek(patoffs)
	outfp.write(struct.pack("<I", t))
	patoffs += 4
	outfp.seek(t)
	
	p = []
	
	# TODO: handle non-64-long tracks!
	for r in xrange(64):
		for ch in xrange(32):
			ti = patlist[i][ch]
			nmask, data = trklist[ti][r]
			if data != None:
				q = ch+1
				if nmask:
					q += 0x80
				p.append(q)
				p += data
		
		p.append(0)
			
	
	outfp.write(struct.pack("<HH", len(p), 64))
	outfp.write("--gm")
	outfp.write(''.join(chr(v) for v in p))

outfp.close()

