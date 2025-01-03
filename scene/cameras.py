#
# Copyright (C) 2023, Inria
# GRAPHDECO research group, https://team.inria.fr/graphdeco
# All rights reserved.
#
# This software is free for non-commercial, research and evaluation use 
# under the terms of the LICENSE.md file.
#
# For inquiries contact  george.drettakis@inria.fr
#

import torch
from torch import nn
import torch.nn.functional as F
import numpy as np
from utils.graphics_utils import getWorld2View2, getProjectionMatrix

class Camera(nn.Module):
    def __init__(self, colmap_id, R, T, FoVx, FoVy, image, gt_alpha_mask,
                 image_name, uid,
                 trans=np.array([0.0, 0.0, 0.0]), scale=1.0, data_device = "cuda"
                 ):
        super(Camera, self).__init__()

        self.uid = uid
        self.colmap_id = colmap_id
        self.R = R
        self.T = T
        self.FoVx = FoVx
        self.FoVy = FoVy
        self.image_name = image_name

        try:
            self.data_device = torch.device(data_device)
        except Exception as e:
            print(e)
            print(f"[Warning] Custom device {data_device} failed, fallback to default cuda device" )
            self.data_device = torch.device("cuda")

        self.original_image = image.clamp(0.0, 1.0).to(self.data_device)
        self.image_width = self.original_image.shape[2]
        self.image_height = self.original_image.shape[1]

        if gt_alpha_mask is not None:
            self.original_image *= gt_alpha_mask.to(self.data_device)
        else:
            self.original_image *= torch.ones((1, self.image_height, self.image_width), device=self.data_device)

        self.zfar = 100.0
        self.znear = 0.01

        self.trans = trans
        self.scale = scale

        self.world_view_transform = getWorld2View2(R, T, trans, scale).T
        self.projection_matrix = getProjectionMatrix(znear=self.znear, zfar=self.zfar, fovX=self.FoVx, fovY=self.FoVy).T
        self.full_proj_transform = np.matmul(self.world_view_transform, self.projection_matrix)
        self.camera_center = np.linalg.inv(self.world_view_transform)[3, :3]
        self.c2w = np.linalg.inv(self.world_view_transform.transpose(0, 1))
        
        v, u = np.meshgrid(np.arange(self.image_height),
                          np.arange(self.image_width), indexing="ij")
        focal_x = self.image_width / (2 * np.tan(self.FoVx * 0.5))
        focal_y = self.image_height / (2 * np.tan(self.FoVy * 0.5))
        rays_d_camera = np.stack([(u - self.image_width / 2 + 0.5) / focal_x,
                               (v - self.image_height / 2 + 0.5) / focal_y,
                               np.ones_like(u)], axis=-1).reshape(-1, 3)
        rays_d = rays_d_camera @ self.world_view_transform[:3, :3].T
        self.rays_d = rays_d / np.linalg.norm(rays_d, axis=-1, keepdims=True)
        self.rays_o = np.broadcast_to(self.camera_center[None], self.rays_d.shape)
        self.rays_rgb = self.original_image.permute(1, 2, 0).reshape(-1, 3)

    def get_rays(self):
        return self.rays_o, self.rays_d
        
    def get_rays_rgb(self):
        return self.rays_rgb
        
    
    
class MiniCam:
    def __init__(self, width, height, fovy, fovx, znear, zfar, world_view_transform, full_proj_transform):
        self.image_width = width
        self.image_height = height    
        self.FoVy = fovy
        self.FoVx = fovx
        self.znear = znear
        self.zfar = zfar
        self.world_view_transform = world_view_transform
        self.full_proj_transform = full_proj_transform
        view_inv = torch.inverse(self.world_view_transform)
        self.camera_center = view_inv[3][:3]

