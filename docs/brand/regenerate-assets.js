// Regenerates the app logo assets from the artwork in this folder.
// Run from the repo root:  node docs/brand/regenerate-assets.js
//
// There is no vector source for the logo, so these PNGs are the masters.
// title.png / logo_1.png ship with white backgrounds; this converts that
// white to real transparency (recovering alpha, then un-premultiplying) so
// the artwork sits cleanly on any surface. Delete this script the day an
// SVG exists.

const fs=require('fs'),zlib=require('zlib');
function decode(file){
  const buf=fs.readFileSync(file);let p=8,w=0,h=0,bd=0,ct=0,idat=[];
  while(p<buf.length){const len=buf.readUInt32BE(p),type=buf.toString('ascii',p+4,p+8),data=buf.slice(p+8,p+8+len);
    if(type==='IHDR'){w=data.readUInt32BE(0);h=data.readUInt32BE(4);bd=data[8];ct=data[9];}
    if(type==='IDAT')idat.push(data); if(type==='IEND')break; p+=12+len;}
  const ch={0:1,2:3,3:1,4:2,6:4}[ct];
  const raw=zlib.inflateSync(Buffer.concat(idat));const stride=w*ch,out=Buffer.alloc(h*stride);let pos=0;
  for(let y=0;y<h;y++){const f=raw[pos++];const line=raw.slice(pos,pos+stride);pos+=stride;
    for(let x=0;x<stride;x++){const a=x>=ch?out[y*stride+x-ch]:0,b=y>0?out[(y-1)*stride+x]:0,c=(x>=ch&&y>0)?out[(y-1)*stride+x-ch]:0;
      let v=line[x];if(f===1)v+=a;else if(f===2)v+=b;else if(f===3)v+=(a+b)>>1;
      else if(f===4){const pp=a+b-c,pa=Math.abs(pp-a),pb=Math.abs(pp-b),pc=Math.abs(pp-c);v+=(pa<=pb&&pa<=pc)?a:(pb<=pc?b:c);}
      out[y*stride+x]=v&255;}}
  return {w,h,ch,out};
}


function crc32(buf){let c,t=[];for(let n=0;n<256;n++){c=n;for(let k=0;k<8;k++)c=c&1?0xEDB88320^(c>>>1):c>>>1;t[n]=c>>>0;}
  let x=0xFFFFFFFF;for(const b of buf)x=t[(x^b)&255]^(x>>>8);return (x^0xFFFFFFFF)>>>0;}
function chunk(type,data){const len=Buffer.alloc(4);len.writeUInt32BE(data.length);
  const td=Buffer.concat([Buffer.from(type,'ascii'),data]);const crc=Buffer.alloc(4);crc.writeUInt32BE(crc32(td));
  return Buffer.concat([len,td,crc]);}
function encodeRGBA(w,h,px){
  const ihdr=Buffer.alloc(13);ihdr.writeUInt32BE(w,0);ihdr.writeUInt32BE(h,4);ihdr[8]=8;ihdr[9]=6;
  const raw=Buffer.alloc(h*(w*4+1));
  for(let y=0;y<h;y++){raw[y*(w*4+1)]=0;px.copy(raw,y*(w*4+1)+1,y*w*4,(y+1)*w*4);}
  return Buffer.concat([Buffer.from([137,80,78,71,13,10,26,10]),chunk('IHDR',ihdr),
    chunk('IDAT',zlib.deflateSync(raw,{level:9})),chunk('IEND',Buffer.alloc(0))]);
}
// Artwork is solid ink composited over white. Recover alpha from how far a
// pixel is from white, then un-premultiply so edges stay clean on any surface.
// `rect` (optional) crops to {x0,y0,x1,y1} inclusive. Cropping matters for
// artwork that goes inline with text: padding baked into the canvas would
// silently shrink the visible mark, since CSS sizes the canvas, not the ink.
function unwhite(file,out,rect){
  const {w,h,ch,out:src}=decode(file);
  const x0=rect?rect.x0:0, y0=rect?rect.y0:0;
  const x1=rect?rect.x1:w-1, y1=rect?rect.y1:h-1;
  const cw=x1-x0+1, chh=y1-y0+1;
  const px=Buffer.alloc(cw*chh*4);
  for(let y=0;y<chh;y++)for(let x=0;x<cw;x++){
    const s=((y+y0)*w+(x+x0))*ch, d=(y*cw+x)*4;
    const r=src[s],g=src[s+1],b=src[s+2];
    const a=255-Math.min(r,g,b);
    if(a===0){px.writeUInt32BE(0,d);continue;}
    const f=a/255;
    const un=(c)=>Math.max(0,Math.min(255,Math.round((c-(1-f)*255)/f)));
    px[d]=un(r);px[d+1]=un(g);px[d+2]=un(b);px[d+3]=a;
  }
  fs.writeFileSync(out,encodeRGBA(cw,chh,px));
  console.log('wrote',out,cw+'x'+chh);
}
// Favicon keeps its navy tile (high contrast in a tab) — just padded to square.
function square(file,out){
  const {w,h,ch,out:src}=decode(file);
  const s=Math.max(w,h),ox=(s-w>>1),oy=(s-h>>1);
  const px=Buffer.alloc(s*s*4);
  const bg=[src[0],src[1],src[2],255];
  for(let i=0;i<s*s;i++){px[i*4]=bg[0];px[i*4+1]=bg[1];px[i*4+2]=bg[2];px[i*4+3]=255;}
  for(let y=0;y<h;y++)for(let x=0;x<w;x++){
    const d=((y+oy)*s+(x+ox))*4,srcI=(y*w+x)*ch;
    px[d]=src[srcI];px[d+1]=src[srcI+1];px[d+2]=src[srcI+2];px[d+3]=255;
  }
  fs.writeFileSync(out,encodeRGBA(s,s,px));
  console.log('wrote',out,s+'x'+s);
}
// Two pieces of artwork ship to the app:
//   logo-icon.png — the tile, left of the wordmark and as the favicon. A full
//                   square; its rounded corners are applied in CSS.
//   ring.png      — the ring, which stands in for the "O" of "Owner". Its
//                   source is on white, so the white becomes real
//                   transparency for it to sit inside a line of text.
// "Next" and "wner" stay live text, so the wordmark scales with the type
// system and can be recoloured for dark mode.
const A='app/src/assets/';
fs.mkdirSync(A,{recursive:true});
square('docs/brand/logo-icon.png',A+'logo-icon.png');
square('docs/brand/logo-icon.png','app/public/favicon.png');
// The ring is cropped straight out of the master lockup rather than taken
// from logo_1.png: title.png's "O" carries the navy arc that logo_1.png (all
// orange) does not, and cropping to the glyph's exact bounds means the CSS
// height is the ring's real diameter. Bounds measured from the artwork —
// the "O" occupies x224-301, y14-91.
unwhite('docs/brand/title.png',A+'ring.png',{x0:224,y0:14,x1:301,y1:91});
