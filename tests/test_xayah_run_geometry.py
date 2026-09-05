"""Keep fixed actor scale without replacing native frame-by-frame anchors."""
import sys
from pathlib import Path
from PIL import Image

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'mods/lol_mod/tools'))
import build_xayah as builder


def test_shared_scale_preserves_measured_native_run_bottoms():
    sources = [Image.new('RGBA',(16,28),(50,40,90,255)) for _ in range(8)]
    scale,bottoms = builder.run_body_geometry(sources)
    assert bottoms == [8,14,18,14,9,12,16,12]
    sizes = []
    for source,(_,_,w,h),bottom in zip(sources,builder.NATIVE_CONTRACT['run']['rects'],bottoms,strict=True):
        frame = builder.fit_actor(source,(w,h),target_height=36,bottom_margin=bottom,fixed_scale=scale)
        x0,y0,x1,y1 = frame.getbbox()
        assert h-y1 == bottom
        sizes.append((x1-x0,y1-y0))
    assert len(set(sizes)) == 1


def test_real_run_source_fits_every_native_frame_with_one_scale():
    sources = builder.split_grid(Image.open(builder.RUN_SOURCE).convert('RGBA'),4,2)
    scale,bottoms = builder.run_body_geometry(sources)
    assert scale > 0
    for source,(_,_,w,h),bottom in zip(sources,builder.NATIVE_CONTRACT['run']['rects'],bottoms,strict=True):
        frame = builder.fit_actor(source,(w,h),target_height=36,bottom_margin=bottom,fixed_scale=scale)
        box = frame.getbbox()
        assert frame.size == (w,h)
        assert h-box[3] == bottom
        assert box[1] > 0 and box[3]-box[1] <= 36
