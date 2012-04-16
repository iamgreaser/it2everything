#!/usr/bin/env python --
#
# smspackgen for IT2VGM
# public domain, 2011, by GreaseMonkey
#
# i don't even care if you don't attribute me with this

import struct

fp = open("smspack.it","wb")

fp.write("IMPMit2vgm pack\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00")
# using IT2.16 versioning as IT2.17 might be mistaken for buttplug
# and that is a BAD THING
fp.write(struct.pack("<HHHHHHHHHBBBBBBHI"
	, 0x1004
	, 2, 0, 3, 0
	, 0x0216, 0x0200
	, 0x0000, 0x0000
	, 128, 32, 6, 125, 128, 0
	, 0, 0))

fp.write("SEGA")
fp.write("\x20"*64+"\x40"*64)
fp.write("\xFF"*2)
smpptrbase = fp.tell()
fp.write("\x00"*(4*3))
fp.write("\x00"*6)
smpoffs = [0,0,0]
smpdatabase = [0,0,0]
SMPNAMES = [
	"[ch1/2/3] SQUARE WAVE",
	"[ch4] WHITE NOISE",
	"[ch4] PERIODIC NOISE",
]

smpdata = [[-120]*16+[120]*16,[],[-120]*(15*16)+[120]*16]

# ripped from vgmplay.py but that's OK as it's my own code
# it's public domain, anyway
tap = 0
tpr = 0x0009
for i in xrange(16):
	tap = (tap<<1)|(tpr&1)
	tpr >>= 1

shadd = 1<<(16-1)
v = shadd
while True:
	q = 120 if v&1 else -120
	smpdata[1] += [q for i in xrange(32)]
	
	v = (v>>1)^(tap if v&1 else 0)
	if v == shadd:
		break

# fix for IT
smpdata[1] = smpdata[1][:len(smpdata[1])//8]
print "buh"

for i in xrange(3):
	t = fp.tell()
	fp.seek(smpptrbase+i*4)
	fp.write(struct.pack("<I",t))
	fp.seek(t)
	fp.write("IMPSSAEEEEEE.GAA\x00")
	fp.write(struct.pack("<BBB", 64, 0x11, 64))
	fp.write(SMPNAMES[i] + "\x00"*(26-len(SMPNAMES[i])))
	fp.write(struct.pack("<BBIIIIIIIBBBB"
		, 0x01, 32
		, len(smpdata[i]), 0, len(smpdata[i]), 8363*8
		, 0, 0, 0
		,0,0,0,0))
	smpdatabase[i] = fp.tell()-8

for i in xrange(3):
	t = fp.tell()
	fp.seek(smpdatabase[i])
	fp.write(struct.pack("<I",t))
	fp.seek(t)
	fp.write(''.join(chr(c&255) for c in smpdata[i]))

