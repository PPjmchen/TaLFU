import cv2
import torch
import torch.nn.functional as F
import numpy as np

# change cv2 image to batched tensor
def numpy_to_torch(a: np.ndarray):
    return torch.from_numpy(a).float().permute(2, 0, 1).unsqueeze(0)

# change batched tensor to cv2 image
def torch_to_numpy(a: torch.Tensor):
    return a.squeeze(0).permute(1,2,0).numpy()

def sample_patch(im: torch.Tensor, pos: torch.Tensor, sample_sz: torch.Tensor, output_sz: torch.Tensor = None,
                 mode: str = 'replicate', max_scale_change=None, is_mask=False):
    
    # get the target's position coord
    posl = pos.long().clone()

    # set padding mode 
    pad_mode = mode
    
    if mode == 'inside' or mode == 'inside_major':
        pad_mode = 'replicate'
        im_sz = torch.Tensor([im.shape[2], im.shape[3]])
        shrink_factor = (sample_sz.float() / im_sz)
        if mode == 'inside':
            shrink_factor = shrink_factor.max()
        elif mode == 'inside_major':
            shrink_factor = shrink_factor.min()
        shrink_factor.clamp_(min=1, max=max_scale_change)
        sample_sz = (sample_sz.float() / shrink_factor).long()

    # Compute pre-downsampling factor
    if output_sz is not None:
        resize_factor = torch.min(sample_sz.float() / output_sz.float()).item()
        df = int(max(int(resize_factor - 0.1), 1))
    else:
        df = int(1)

    sz = sample_sz.float() / df     # new size

    # Do downsampling
    if df > 1:
        os = posl % df              # offset
        posl = (posl - os) // df    # new position
        im2 = im[..., os[0].item()::df, os[1].item()::df]   # downsample
    else:
        im2 = im

    # compute size to crop
    szl = torch.max(sz.round(), torch.Tensor([2])).long()

    # Extract top and bottom coordinates
    tl = posl - (szl - 1) // 2
    br = posl + szl//2 + 1

    # Shift the crop to inside
    if mode == 'inside' or mode == 'inside_major':
        im2_sz = torch.LongTensor([im2.shape[2], im2.shape[3]])
        shift = (-tl).clamp(0) - (br - im2_sz).clamp(0)
        tl += shift
        br += shift

        outside = ((-tl).clamp(0) + (br - im2_sz).clamp(0)) // 2
        shift = (-tl - outside) * (outside > 0).long()
        tl += shift
        br += shift

    # Get image patch
    if not is_mask:
        im_patch = F.pad(im2, (-tl[1].item(), br[1].item() - im2.shape[3], -tl[0].item(), br[0].item() - im2.shape[2]), pad_mode)
    else:
        im_patch = F.pad(im2, (-tl[1].item(), br[1].item() - im2.shape[3], -tl[0].item(), br[0].item() - im2.shape[2]))

    # Get image coordinates
    patch_coord = df * torch.cat((tl, br)).view(1,4)
    
    if output_sz is None or (im_patch.shape[-2] == output_sz[0] and im_patch.shape[-1] == output_sz[1]):
        return im_patch.clone(), patch_coord

    # Resample to ouput size
    if not is_mask:
        im_patch = F.interpolate(im_patch, output_sz.long().tolist(), mode='bilinear')
    else:
        im_patch = F.interpolate(im_patch, output_sz.long().tolist(), mode='nearest')

    return im_patch, patch_coord

def main():
    img = cv2.imread('test_img.jpg')
    img = numpy_to_torch(img)
    pos = torch.tensor([108.5000, 387.0000])
    sample_size = torch.tensor([80, 80])
    output_size = torch.tensor([500, 500])

    im_patch, _ = sample_patch(img, pos, sample_size, output_size, )
    im_patch = torch_to_numpy(im_patch)
    cv2.imwrite('test_img2.jpg', im_patch)


if __name__ == '__main__':
    main()