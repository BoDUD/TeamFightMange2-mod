"""Inspect the exact packed anatomical source at native timing and anchoring."""
import json
from PIL import Image,ImageDraw,ImageOps
import build_yone as b
from yone_run_anatomy import verify_packed

def build():
    frames,manifest,audits=b._load_native_v7_body_frames()
    info=manifest['run_pixel_edit']
    sheet=Image.open(b.ACTOR_DIR/'yone_v7#sheet.png').convert('RGBA')
    out=b.MOD_ROOT.parents[1]/'output/yone_anatomy_packed';out.mkdir(parents=True,exist_ok=True)
    contact=Image.new('RGB',(1760,320),'#20242e');d=ImageDraw.Draw(contact)
    playback=[]
    for i,row in enumerate(info['frames']):
        x,y,w,h=b.NATIVE_CONTRACT['run']['rects'][i]
        actual=sheet.crop((x,y,x+w,y+h))
        source=Image.open(b.NATIVE_V7_ROOT/f'frames/run_{i:02}.png').convert('RGBA')
        verify_packed(source,actual,i)
        row['packed_bytes_verified']=True
        large=actual.resize((w*5,h*5),Image.Resampling.NEAREST)
        contact.paste(large,(i*220,20),large)
        d.text((i*220,0),f'{i} / anatomical source',fill='white')
        stage=Image.new('RGB',(340,150),'#20242e');sd=ImageDraw.Draw(stage)
        sd.line((0,121,339,121),fill='#434956')
        for center,pix in ((85,actual),(255,ImageOps.mirror(actual))):
            pix=pix.resize((w*2,h*2),Image.Resampling.NEAREST)
            stage.paste(pix,(center-w,100-h),pix)
        playback.append(stage)
    d.text((12,290),'Original upper body; eight redrawn leg sources. Offline proof, NOT live motion acceptance.',fill='white')
    contact.save(out/'contact.png')
    playback[0].save(out/'run.gif',save_all=True,append_images=playback[1:],duration=80,loop=0,disposal=2)
    b.write_json(b.QA_DIR/'yone_run_pixel_edit.json',info)
    # Refresh only this run's provenance; leave other art/skill/UI audits alone.
    report_path=b.QA_DIR/'yone_imagegen_sources.json'
    report=json.loads(report_path.read_text(encoding='utf8'))
    report['body_source']['run_pixel_edit']=info
    for i in range(8):
        report['body_frames'][f'run[{i}]']=audits[f'run[{i}]']
    b.write_json(report_path,report)
    print(out)

if __name__=='__main__':build()
