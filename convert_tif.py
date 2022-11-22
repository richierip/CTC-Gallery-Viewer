'''
This script contains code that will convert a large tif to a memory mapped format 
    for faster loading with the gallery viewer application. This will only have to be run once.
'''

import tifffile
import numpy as np
# import re
import time

input_image = r"C:\Users\prich\Desktop\Projects\MGH\CTC_Example\Exp02a01_02_Scan1.qptiff"

with tifffile.Timer(f'\nLoading pyramid from {input_image} into RAM...\n'):
    pyramid = tifffile.imread(input_image)
    pyramid = np.transpose(pyramid,(2,1,0))
    # pyramid = pyramid[:2000,:2000,1]
    print('... completed in ', end='')


print(f"\n shape is {pyramid.shape}\n")

print(f'\nCreating memory-mapped tif...\n')
cur = time.time()
new_name = "memory_mapped_array.tif" #TODO make a default that is a modification 
mm_image = tifffile.memmap(new_name, shape = pyramid.shape, dtype=pyramid.dtype,photometric='minisblack')
print("Created empty .tif")
mm_image[:] = pyramid[:]
print("Passed data")
print(f'... completed in {time.time()-cur}', end='')


cur = time.time()
print("\nWriting to disk...")
mm_image.flush() # Write to disk
print(f'... completed in {time.time()-cur}', end='')