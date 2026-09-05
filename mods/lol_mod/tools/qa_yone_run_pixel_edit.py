"""Inspect the packed run at native timing, including opposite facing.

This is offline asset QA. It deliberately does not claim a live battle pass.
"""
import json
from pathlib import Path
from PIL import Image,ImageDraw,ImageOps
import build_yone as b
from yone_run_pixel_edit import verify_packed

def build():
    mod=b.MOD_ROOT
    frames,manifest,audits=b._load_native_v7_body_frames()
    info=manifest['run_pixel_edit']
    sheet=Image.open(b.ACTOR_DIR/'yone_v7#sheet.png').convert('RGBA')
    palette=json.loads((b.NATIVE_V7_ROOT/'palette.json').read_text())
    weapons={tuple(c['rgba']) for c in palette['colors'] if c['role'].startswith(('steel_','azakana_'))}
    out=mod.parents[1]/'output/yone_leg_edit';out.mkdir(parents=True,exist_ok=True)
    contact=Image.new('RGB',(1760,320),'#20242e');d=ImageDraw.Draw(contact)
    playback=[]
    for i,row in enumerate(info['frames']):
        x,y,w,h=b.NATIVE_CONTRACT['run']['rects'][i]
        actual=sheet.crop((x,y,x+w,y+h))
        source=Image.open(b.NATIVE_V7_ROOT/f'frames/run_{i:02}.png').convert('RGBA')
        verify_packed(source,actual,i,row['pelvis_x'],row['floor_y'],weapons)
        row['packed_bytes_verified']=True
        large=actual.resize((w*5,h*5),Image.Resampling.NEAREST)
        contact.paste(large,(i*220,20),large)
        d.text((i*220,0),f"{i} / {row['support_anatomical_leg']} support",fill='white')
        stage=Image.new('RGB',(340,130),'#20242e');sd=ImageDraw.Draw(stage)
        sd.line((0,99,339,99),fill='#434956')
        for center,pix in ((85,actual),(255,ImageOps.mirror(actual))):
            pix=pix.resize((w*2,h*2),Image.Resampling.NEAREST)
            stage.paste(pix,(center-w,98-row['floor_y']*2),pix)
        playback.append(stage)
    d.text((12,290),'Packed native frames; upper body + both swords unchanged. Offline review, not a live battle capture.',fill='white')
    contact.save(out/'contact.png')
    playback[0].save(out/'run.gif',save_all=True,append_images=playback[1:],duration=80,loop=0,disposal=2)
    report=b.QA_DIR/'yone_run_pixel_edit.json'
    b.write_json(report,info)
    print(out)

if __name__=='__main__': build()
