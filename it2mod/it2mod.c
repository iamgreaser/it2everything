#include <stdlib.h>
#include <errno.h>
#include <string.h>
#include <unistd.h>
#include <stdio.h>

#include <stdint.h>

#ifndef LITTLE_ENDIAN
// Comment this line if you're using a big-endian machine
#define LITTLE_ENDIAN
#endif

#define UBYTE unsigned char
#define SBYTE signed char
#define UWORD unsigned short
#define SWORD signed short
#define ULONG unsigned int
#define SLONG signed int

#ifdef LITTLE_ENDIAN
#define SWAPLE16(v) (((UWORD)v >> 8)|((UWORD)v << 8))
#define SWAPBE16(v) v
#define SWAPLE32(v) ((ULONG)SWAPLE16(v >> 16)|((ULONG)SWAPLE16(v & 0xFFFF) << 16))
#define SWAPBE32(v) v
#else
#define SWAPLE16(v) v
#define SWAPBE16(v) (((UWORD)v >> 8)|((UWORD) v << 8))
#define SWAPLE32(v) v
#define SWAPBE32(v) ((ULONG)SWAPBE16(v >> 16)|((ULONG)SWAPBE16(v & 0xFFFF) << 16))
#endif

struct it_header_impm
{
	UBYTE magic[4];
	UBYTE mname[26];
	UWORD philight;
	UWORD ordnum;
	UWORD insnum;
	UWORD smpnum;
	UWORD patnum;
	UWORD cwtv;
	UWORD cmwt;
	UWORD flags;
	UWORD special;
	UBYTE gv;
	UBYTE mv;
	UBYTE is;
	UBYTE it;
	UBYTE sep;
	UBYTE pwd;
	UWORD msglen;
	ULONG msgoffs;
	ULONG reserved;
	UBYTE chanpan[64];
	UBYTE chanvol[64];
};

/*
        0   1   2   3   4   5   6   7   8   9   A   B   C   D   E   F
      ÚÄÄÄÂÄÄÄÂÄÄÄÂÄÄÄÂÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄ¿
0000: ³'I'³'M'³'P'³'S'³ DOS Filename (12345678.123)                   ³
      ÃÄÄÄÅÄÄÄÅÄÄÄÅÄÄÄÅÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄŽ
0010: ³00h³GvL³Flg³Vol³ Sample Name, max 26 bytes, includes NUL.......³
      ÃÄÄÄÁÄÄÄÁÄÄÄÁÄÄÄÁÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÂÄÄÄÂÄÄÄŽ
0020: ³.......................................................³Cvt³DfP³
      ÃÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÂÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÂÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÂÄÄÄÄÄÄÄÁÄÄÄÁÄÄÄŽ
0030: ³ Length        ³ Loop Begin    ³ Loop End      ³ C5Speed       ³
      ÃÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÅÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÅÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÅÄÄÄÂÄÄÄÂÄÄÄÂÄÄÄŽ
0040: ³ SusLoop Begin ³ SusLoop End   ³ SamplePointer ³ViS³ViD³ViR³ViT³
      ÀÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÁÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÁÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÁÄÄÄÁÄÄÄÁÄÄÄÁÄÄÄÙ
*/

struct it_header_imps
{
	UBYTE magic[4];
	UBYTE fname[13];
	UBYTE gvl;
	UBYTE flg;
	UBYTE vol;
	UBYTE name[26];
	UBYTE cvt;
	UBYTE dfp;
	ULONG length;
	ULONG loopbeg;
	ULONG loopend;
	ULONG c5speed;
	ULONG susbeg;
	ULONG susend;
	ULONG pointer;
	UBYTE vis, vid, vir, vit;
};

struct mod_samphead
{
	UWORD len;
	UBYTE ftune, vol;
	UWORD lpbeg;
	UWORD lplen;
};

UWORD pertab[60] = {
	1712,1616,1525,1440,1357,1281,1209,1141,1077,1017, 961, 907,
	 856, 808, 762, 720, 678, 640, 604, 570, 538, 508, 480, 453,
	 428, 404, 381, 360, 339, 320, 302, 285, 269, 254, 240, 226,
	 214, 202, 190, 180, 170, 160, 151, 143, 135, 127, 120, 113,
	 107, 101,  95,  90,  85,  80,  76,  71,  67,  64,  60,  57
};

ULONG sit2mod(struct it_header_imps *imps, ULONG v)
{
	if(imps->c5speed == 0)
		return v;
	
	ULONG l = (v & 0xFFFF) * 8363;
	ULONG m = (v >> 16) * 8363;
	
	m += l >> 16; l &= 0xFFFF;
	//printf("m = %08X\n", m);
	//printf("l = %08X\n", l);
	l += (m % imps->c5speed) << 16;
	m /= imps->c5speed;
	l /= imps->c5speed;
	
	//printf("m = %08X\n", m);
	//printf("l = %08X\n", l);
	return (m << 16) + l;
};

ULONG smod2it(struct it_header_imps *imps, ULONG v)
{
	if(imps->c5speed == 0)
		return v;
	
	ULONG l = (v & 0xFFFF) * (imps->c5speed & 0xFFFF);
	ULONG m = (v >> 16) * (imps->c5speed & 0xFFFF) + (v & 0xFFFF) * (imps->c5speed >> 16);
	ULONG h = (v >> 16) * (imps->c5speed >> 16);
	
	m += l >> 16; l &= 0xFFFF;
	h += m >> 16; m &= 0xFFFF;
	m += (h % 8363) << 16;
	h /= 8363;
	l += (m % 8363) << 16;
	m /= 8363;
	l /= 8363;
	
	//printf("h = %08X\n", h);
	//printf("m = %08X\n", m);
	//printf("l = %08X\n", l);
	return (m << 16) + l;
};

int main(int argc, char *argv[])
{
	int i, j, k;
	
	if(argc <= 2)
	{
		printf("usage:\n\t%s infile.it outfile.mod\n", argv[0]);
		return 99;
	};
	
	FILE *it = fopen(argv[1], "rb");
	if(it == NULL)
	{
		printf("error %i reading IT file: %s\n", errno, strerror(errno));
		return 102;
	};
	
	struct it_header_impm impm;
	
	fread(&impm, sizeof(struct it_header_impm), 1, it);
	
	if(impm.magic[0] != 'I' || impm.magic[1] != 'M' || impm.magic[2] != 'P' || impm.magic[3] != 'M')
	{
		printf("this is not an IT file - IMPM not matched\n");
		fclose(it);
		return 102;
	};
	
	impm.insnum = SWAPBE16(impm.insnum);
	impm.smpnum = SWAPBE16(impm.smpnum);
	impm.patnum = SWAPBE16(impm.patnum);
	
	UBYTE ordtab[256];
	ULONG iptrs[256];
	ULONG sptrs[256];
	ULONG pptrs[256];
	
	fread(&ordtab[0], 1, impm.ordnum, it);
	fread(&iptrs[0], 4, impm.insnum, it);
	fread(&sptrs[0], 4, impm.smpnum, it);
	fread(&pptrs[0], 4, impm.patnum, it);
	
	FILE *mod = fopen(argv[2], "wb");
	if(mod == NULL)
	{
		printf("error %i writing MOD file: %s\n", errno, strerror(errno));
		fclose(it);
		return 103;
	};
	
	fwrite(&impm.mname[0], 20, 1, mod);
	
	struct it_header_imps imps[31];
	struct mod_samphead samphead[31];
	
	// Sample data.
	for(i = 0; i < 31 && i < impm.smpnum; i++)
	{	
		ULONG len,lpstart,lplen;
		
		fseek(it, SWAPBE32(sptrs[i]), SEEK_SET);
		fread(&imps[i], sizeof(struct it_header_imps), 1, it);
		fwrite(&imps[i].name[0], 22, 1, mod);
		
		printf("sample %i len %04X\n", i, SWAPBE32(imps[i].length));
		
		if(imps[i].flg & 0x10)
		{
			lpstart = sit2mod(&imps[i], SWAPBE32(imps[i].loopbeg)) / 2;
			if(imps[i].flg & 0x40)
			{
				len = sit2mod(&imps[i], SWAPBE32(imps[i].loopend)*2 - SWAPBE32(imps[i].loopbeg)) / 2;
				lplen = sit2mod(&imps[i], (SWAPBE32(imps[i].loopend) - SWAPBE32(imps[i].loopbeg))) / 2;
				printf("pingpong\n");
			} else {
				len = sit2mod(&imps[i], SWAPBE32(imps[i].loopend)) / 2;
				//len = sit2mod(&imps[i], SWAPBE32(imps[i].length)) / 2;
				lplen = sit2mod(&imps[i], (SWAPBE32(imps[i].loopend) - SWAPBE32(imps[i].loopbeg))) / 2;
				printf("loop\n");
			};
		} else
			lplen = 1;
		
		if(lplen <= 1)
		{
			lplen = 1;
			lpstart = 0;
			len = sit2mod(&imps[i], SWAPBE32(imps[i].length)) / 2;
			printf("onetime\n");
		};
		
		printf("smp %i, len %i, loop %04X-%04X\n", i, len, lpstart, lplen);
		
		
		samphead[i].ftune = 0x00;
		samphead[i].vol = imps[i].vol;
		
		if(len > 0xFFFF)
			len = 0xFFFF;
		
		samphead[i].len = SWAPLE16(len);
		samphead[i].lpbeg = SWAPLE16(lpstart);
		samphead[i].lplen = SWAPLE16(lplen);
		
		fwrite(&samphead[i], sizeof(struct mod_samphead), 1, mod);
		
		samphead[i].len = len;
		samphead[i].lpbeg = lpstart;
		samphead[i].lplen = lplen;
	};
	
	// Any extra samples to write?
	for(; i < 31; i++)
	{
		UBYTE xbuf[30] = {
			0,0,0,0,0,
			0,0,0,0,0,
			0,0,0,0,0,
			0,0,0,0,0,
			0,0,
			
			0,0,
			0,
			0,
			0,0,
			0,1
		};
		
		fwrite(&xbuf[0], 30, 1, mod);
	};
	
	// Orders. Scan through the list until you hit a 255.
	// If that doesn't happen, then we clip it at 128 orders.
	impm.patnum = 0;
	
	for(i = 0; i < 128; i++)
	{
		if(ordtab[i] == 255)
			break;
		if(ordtab[i] >= impm.patnum)
			impm.patnum = ordtab[i]+1;
	};
	
	impm.ordnum = i;
	
	for(; i < 128; i++)
		ordtab[i] = 0;
	
	i = impm.ordnum;
	
	// Now write it all.
	{
		UBYTE b;
		b = i;
		fwrite(&b, 1, 1, mod);
		b = 127;
		fwrite(&b, 1, 1, mod);
		fwrite(&ordtab[0], 1, 128, mod);
		
		// If you're using more than 4 channels, I will not be happy.
		// You're a pagan for doing so.
		UBYTE mk[4] = {'M', '.', 'K', '.'};
		
		if(impm.patnum > 64)
			mk[1] = mk[3] = '!';
		
		fwrite(&mk[0], 4, 1, mod);
	};
	
	// Patterns
	UWORD fwds[4];
	UBYTE lmask[64];
	UBYTE lnote[64];
	UBYTE lsamp[64];
	UBYTE lvol[64];
	UBYTE lefftype[64];
	UBYTE leffparam[64];
	int lsay[64];
	UBYTE chanvar, chansel;
	
	for(i = 0; i < impm.patnum; i++)
	{
		fseek(it, SWAPBE32(pptrs[i]), SEEK_SET);
		
		fread(&fwds[0], 2, 4, it);
		
		for(j = 0; j < 64; j++)
			lmask[j] = lnote[j] = lsamp[j] = lvol[j] = lefftype[j] = leffparam[j] = 0;
		
		fwds[0] = SWAPBE32(fwds[0]); // Packed data length	
		fwds[1] = SWAPBE32(fwds[1]); // Rows - this should be 64.
		
		for(j = 0; j < 64; j++)
		{
			for(k = 0; k < 64; k++)
				lsay[k] = 0;
			
			for(;;)
			{
				fread(&chanvar, 1, 1, it);
				if(chanvar == 0)
					break;
				
				chansel = (chanvar-1) & 0x3F;
				
				lsay[chansel] = !0;
				
				if(chanvar & 0x80)
					fread(&lmask[chansel], 1, 1, it);

				if(lmask[chansel] & 0x01)
					fread(&lnote[chansel], 1, 1, it);
				if(lmask[chansel] & 0x02)
					fread(&lsamp[chansel], 1, 1, it);
				if(lmask[chansel] & 0x04)
					fread(&lvol[chansel], 1, 1, it);
				if(lmask[chansel] & 0x08)
				{
					fread(&lefftype[chansel], 1, 1, it);
					fread(&leffparam[chansel], 1, 1, it);
				};
			};
			
			for(k = 0; k < 4; k++)
			{
				ULONG towrite = 0x00000000;
				//printf("ch %02i row %02i mask %02X\n", k, j, lmask[k]);
				if(lsay[k])
				{
					if(lmask[k] & 0x11)
					{
						if(lnote[k] >= 36 && lnote[k] < 96)
							towrite |= pertab[lnote[k]-36] << 16;
						else
							towrite |= 0xC00;
					}
					if(lmask[k] & 0x22)
						towrite |= ((lsamp[k] & 0x0F) << 12)|((lsamp[k] & 0xF0) << 24);
					if((lmask[k] & 0x44) && lvol[k] <= 64)
						towrite |= 0xC00 | lvol[k];
					else if(lmask[k] & 0x88)
					{
						switch(lefftype[k] + 'A' - 1)
						{
							case 'A':
								towrite |= 0xF00 | leffparam[k];
								break;
							case 'B':
								towrite |= 0xB00 | leffparam[k];
								break;
							case 'C':
								towrite |= 0xD00 | (leffparam[k] % 10) | ((leffparam[k] / 10) << 4);
								break;
							case 'D':
								if((leffparam[k] & 0xF0) == 0xF0)
									towrite |= 0xEB0 | (leffparam[k] & 15);
								else if((leffparam[k] & 0x0F) == 0x0F)
									towrite |= 0xEA0 | ((leffparam[k] >> 4) & 15);
								else
									towrite |= 0xA00 | leffparam[k];
								break;
							case 'E':
								if(leffparam[k] >= 0xE0)
								{
									if(leffparam[k]-0xE0 >= 0x10)
										towrite |= 0xE20 | (leffparam[k] - 0xF0);
									else
										towrite |= 0xE20 | ((leffparam[k]-0xE0+2)/4);
								} else
									towrite |= 0x200 | leffparam[k];
								break;
							case 'F':
								if(leffparam[k] >= 0xE0)
								{
									if(leffparam[k]-0xE0 >= 0x10)
										towrite |= 0xE10 | (leffparam[k] - 0xF0);
									else
										towrite |= 0xE10 | ((leffparam[k]-0xE0+2)/4);
								} else
									towrite |= 0x100 | leffparam[k];
								break;
							case 'G':
								towrite |= 0x300 | leffparam[k];
								break;
							case 'H':
								towrite |= 0x400 | leffparam[k];
								break;
							case 'J':
								towrite |= leffparam[k];
								break;
							case 'K':
								towrite |= 0x600 | leffparam[k];
								break;
							case 'L':
								towrite |= 0x500 | leffparam[k];
								break;
							case 'O':
								towrite |= 0x900 | leffparam[k];
								break;
							case 'Q':
								towrite |= 0xE90 | (leffparam[k] & 0x0F);
								break;
							case 'R':
								towrite |= 0x700 | leffparam[k];
								break;
							case 'S':
								switch((leffparam[k] >> 4) & 0x0F)
								{
									case 0x0:
										towrite |= 0xE00 | (leffparam[k] & 0x0F);
										break;
									case 0x3:
										towrite |= 0xE40 | (leffparam[k] & 0x0F);
										break;
									case 0x4:
										towrite |= 0xE70 | (leffparam[k] & 0x0F);
										break;
									case 0x6:
										towrite |= 0xEE0 | (leffparam[k] & 0x0F);
										break;
									case 0xB:
										towrite |= 0xE60 | (leffparam[k] & 0x0F);
										break;
									case 0xC:
										towrite |= 0xEC0 | (leffparam[k] & 0x0F);
										break;
									case 0xD:
										towrite |= 0xED0 | (leffparam[k] & 0x0F);
										break;
									case 0xE:
										towrite |= 0xEE0 | (leffparam[k] & 0x0F);
										break;
								}
								break;
							case 'T':
								if(leffparam[k] >= 0x20 || leffparam[k] == 0x00)
									towrite |= 0xF00 | leffparam[k];
								break;
							case 'U':
								towrite |= 0x400 | (leffparam[k] & 0xF0) | ((leffparam[k] & 0x0F)/4);
								break;
						};
					};
				};
				
#ifdef LITTLE_ENDIAN
				UBYTE bswp[4];
				
				bswp[3] = towrite & 0xFF; towrite >>= 8;
				bswp[2] = towrite & 0xFF; towrite >>= 8;
				bswp[1] = towrite & 0xFF; towrite >>= 8;
				bswp[0] = towrite & 0xFF; towrite >>= 8;
				
				fwrite(&bswp[0], 4, 1, mod);
#else
				fwrite(&towrite, 4, 1, mod);
#endif
			};
		};
	};
	
	// Sample data
	for(i = 0; i < impm.smpnum && i < 31; i++)
	{
		int len = sit2mod(&imps[i], SWAPBE32(imps[i].length));
		int revlen = samphead[i].len*2;
		
		if(len <= 0)
			continue;
		
		char buf[imps[i].length];
		
		fseek(it, imps[i].pointer, SEEK_SET);
		fread(&buf[0], imps[i].length, 1, it);
		
		SBYTE b;
		
		for(j = 0; j < 0x20000 && j < len && j < revlen; j++)
		{
			b = buf[smod2it(&imps[i], j)];
			if(!(imps[i].cvt & 0x01))
				b -= 0x80;
			
			fwrite(&b, 1, 1, mod);
		};
		
		if(imps[i].flg & 0x40)
		{
			for(k = j; j < 0x20000 && j < revlen; k--, j++)
			{
				b = buf[smod2it(&imps[i], k)];
			
				if(!(imps[i].cvt & 0x01))
					b -= 0x80;
			
				fwrite(&b, 1, 1, mod);
			};
		};
		
		for(; j < 0x20000 && j < revlen; j++)
			fwrite(&b, 1, 1, mod);
	};
	
	fclose(mod);
	fclose(it);
	return 0;
};

