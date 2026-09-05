"""Pack individually hand-drawn leg cels, with no build-time pose synthesis.

All eight final-resolution images are immutable authored sources. The original
head, torso, arms and connected swords remain byte-exact. Old thin/widened row
patches are deliberately not imported. Live motion quality is a separate gate.
"""
import hashlib
import json
from pathlib import Path
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]/'source/native/yone_run_handdrawn'

def digest(image):
    return hashlib.sha256(image.tobytes()).hexdigest()

def load_frame(original,index):
    manifest=json.loads((ROOT/'frames.json').read_text(encoding='utf8'))
    if [r['index'] for r in manifest['frames']]!=list(range(8)):
        raise ValueError('Anatomical run source must contain exactly eight frames')
    if hashlib.sha256((ROOT/manifest['source_file']).read_bytes()).hexdigest()!=manifest['source_sha256']:
        raise ValueError('Hand-drawn pixel source hash changed')
    row=manifest['frames'][index]
    if digest(original)!=row['base_rgba_sha256']:
        raise ValueError('Yone base model changed; review anatomical source')
    frame=Image.open(ROOT/row['file']).convert('RGBA')
    protected=Image.open(ROOT/row['protected_mask']).convert('L')
    if frame.size!=original.size or list(frame.size)!=row['size'] or protected.size!=frame.size:
        raise ValueError('Native anatomical frame size changed')
    if digest(frame)!=row['rgba_sha256'] or digest(protected)!=row['protected_sha256']:
        raise ValueError('Authored anatomical pixels changed')
    for y in range(frame.height):
        for x in range(frame.width):
            color=frame.getpixel((x,y))
            if color[3] not in (0,255) or (not color[3] and color!=(0,0,0,0)):
                raise ValueError('Anatomical source alpha is not clean binary RGBA')
            if protected.getpixel((x,y)) or y<row['original_upper_body_rows']:
                if color!=original.getpixel((x,y)):
                    raise ValueError('Original protected upper body or weapon changed')
    box=frame.getbbox()
    if list(box)!=row['alpha_bbox'] or not(0<box[0]<box[2]<frame.width and 0<box[1]<box[3]<frame.height):
        raise ValueError('Anatomical source clips native frame edge')
    for x,y,w,h in row['feet']:
        if not frame.crop((x,y,x+w,y+h)).getbbox():
            raise ValueError('Authored visible boot annotation is empty')
    return frame,row

def verify_packed(original,actual,index):
    expected,_=load_frame(original,index)
    if actual.size!=expected.size or actual.tobytes()!=expected.tobytes():
        raise ValueError(f'run[{index}] packed anatomy differs from authored pixels')

def apply_to_frames(frames,audits):
    report=[]
    for i in range(8):
        result,row=load_frame(frames[('run',i)],i)
        frames[('run',i)]=result
        audits[f'run[{i}]'].update(
            foot_zones=row['feet'],pack_transform='authored anatomical leg source byte copy',
            anatomy_source=f'source/native/{ROOT.name}/{row["file"]}',
            source_alpha_bbox=list(result.getbbox()),packed_rgba_sha256=row['rgba_sha256'])
        report.append(row)
    return report
