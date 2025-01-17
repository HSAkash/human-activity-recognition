import os
import cv2
import shutil
import numpy as np
from glob import glob
from tqdm import tqdm
from pathlib import Path
from humanActivityRecognition import logger
from concurrent.futures import ThreadPoolExecutor, as_completed
from humanActivityRecognition.entity.config_entity import DataAugmentationConfig

class ImageAugmentation:
    def __init__(self, config: DataAugmentationConfig):
        self.config = config


    def rotate_image(self, image, angle):
        """
        Rotate an image by the specified angle.

        Args:
            image: The input image as a NumPy array.
            angle: The angle to rotate the image.

        Returns:
            The rotated image.
        """
        # Get the image dimensions
        height, width = image.shape[:2]

        # Calculate the rotation matrix
        rotation_matrix = cv2.getRotationMatrix2D((width / 2, height / 2), angle, 1)

        # Perform the rotation
        rotated_image = cv2.warpAffine(image, rotation_matrix, (width, height))

        return rotated_image

    def flip_image(self, image):
        """
        Flip an image horizontally.

        Args:
            image: The input image as a NumPy array.

        Returns:
            The flipped image.
        """
        return cv2.flip(image, 1)
    

    def process_image(self, img):
        h, w = img.shape[:2]
        pad_h = max(0, (self.config.IMAGE_HEIGHT - h) // 2)
        pad_w = max(0, (self.config.IMAGE_WIDTH - w) // 2)
        img = np.pad(img, ((pad_h, pad_h), (pad_w, pad_w), (0, 0)), mode='constant', constant_values=0)
        crop_h = max(0, (h-self.config.IMAGE_HEIGHT) // 2)
        crop_w = max(0, (w-self.config.IMAGE_WIDTH) // 2)
        img = img[crop_h:self.config.IMAGE_HEIGHT+crop_h, crop_w:self.config.IMAGE_WIDTH+crop_w, :]
        return img

    def scale_image(self, image, scale_factor):
        """
        Scale an image by the specified factor.

        Args:
            image: The input image as a NumPy array.
            scale_factor: The factor by which to scale the image.

        Returns:
            The scaled image.
        """
        # Get the image dimensions
        height, width = image.shape[:2]

        # Calculate the new dimensions
        new_height = int(height * scale_factor)
        new_width = int(width * scale_factor)

        # Resize the image
        scaled_image = cv2.resize(image, (new_width, new_height))

        return self.process_image(scaled_image)
    
    def get_dest_path(self, img_path: Path, source_dir: Path, dist_dir: Path, aug_type: str, extra_arg: str=''):
        '''
        This function will return the destination path of the augmented image.
        Args:
            img_path: The path of the image.
            source_dir: The source directory of the image.
            dist_dir: The destination directory of the augmented image.
            aug_type: The type of augmentation.
            extra_arg: Extra argument for the augmented image.
        '''

        dist_path = img_path.replace(source_dir, dist_dir)
        dist_path = dist_path.split('/')
        dist_path[-2] = f"{dist_path[-2]}_{aug_type}_{extra_arg}"
        return '/'.join(dist_path)


    def apply_augmentation(self, img_path: Path):
        '''
        This function will apply the augmentation to the images.
        Args:
            img_path: The path of the image.
            aug_dir: The path of the augmented image directory.
        '''

        # check if the image is already augmented
        dest_path = self.get_dest_path(
                img_path=img_path,
                source_dir=self.config.blured_split_dir,
                dist_dir=self.config.blured_aug_dir,
                aug_type='flip')
        
        if os.path.exists(dest_path):
            return


        img = cv2.imread(str(img_path))
        # Rotate the image by the specified angles
        for angle in self.config.ROTATE_FACTORS:
            dest_path = self.get_dest_path(
                img_path=img_path,
                source_dir=self.config.blured_split_dir,
                dist_dir=self.config.blured_aug_dir,
                aug_type='rotate',
                extra_arg=f"{angle}")
            rotated_image = self.rotate_image(img, angle)
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            cv2.imwrite(dest_path, rotated_image)

        # Scale the image by the specified factors
        for scale_factor in self.config.SCALE_FACTORS:
            dest_path = self.get_dest_path(
                img_path=img_path,  # Change to keyword argument
                source_dir=self.config.blured_split_dir,
                dist_dir=self.config.blured_aug_dir,
                aug_type='scale',
                extra_arg=scale_factor)
            scaled_image = self.scale_image(img, scale_factor)
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            cv2.imwrite(dest_path, scaled_image)
        
        # Flip the image horizontally
        if self.config.FLIP_FACTOR:
            dest_path = self.get_dest_path(
                img_path=img_path,
                source_dir=self.config.blured_split_dir,
                dist_dir=self.config.blured_aug_dir,
                aug_type='flip')
            flipped_image = self.flip_image(img)
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            cv2.imwrite(dest_path, flipped_image)
    
    def run(self):
        '''
        This function will apply the augmentation to the images.
        '''
        # Get the list of image files.
        image_files = glob(os.path.join(self.config.blured_split_dir, 'train','*','*', '*'))
        # Create a list to store the tasks.
        tasks = []

        with ThreadPoolExecutor(max_workers=self.config.MAX_WORKERS) as executor:
            # Iterate over each image file.
            for image_file in image_files:
                tasks.append(
                    executor.submit(self.apply_augmentation, image_file)
                )

            # Wait for the tasks to complete.
            for task in tqdm(as_completed(tasks), total=len(tasks), desc="Applying Augmentation"):
                task.result()

        # Copying main images
        shutil.copytree(self.config.blured_split_dir, self.config.blured_aug_dir, dirs_exist_ok=True)

        logger.info('Image augmentation completed.')
