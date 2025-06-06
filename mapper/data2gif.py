import os
import matplotlib.pyplot as plt
plt.rcParams.update({'figure.max_open_warning': 0})
import imageio
from mapper.filename_utils import unify_filename, fix_unicode
from functools import partial
from multiprocessing.pool import ThreadPool

def create_gif(filename, idx, parameters_to_read):
    
    return
    
    path = os.path.normpath(filename).split(os.path.sep)
    name = path[-1]
    
    try:
        name = name[:len(name) - name[::-1].index('.') - 1]
    except ValueError:
        pass
    if ':' in name:
        name = name.replace(':', '')
    name = unify_filename(name)
    name = name[:(len(name) - name[::-1].find('-') - 1)]
    cur_dir = os.path.join(*path[:path.index('data_files')])
    cur_dir = fix_unicode(cur_dir)
    tomake_gif = os.path.join(cur_dir, '2d_maps', 'images', f'{name}_{idx}', 
                           'gifs')

    tomake_gif = fix_unicode(tomake_gif)

    if not os.path.exists(tomake_gif):
        try:
            os.makedirs(tomake_gif)
        except FileExistsError:
            pass

    path_files = os.path.join(cur_dir, '2d_maps', 'images', f'{name}_{idx}')
    path_files = fix_unicode(path_files)

    image_files = []
    for (root, dir_names, file_names) in os.walk(path_files):
        for i in file_names:
            if '.png' in i:
                file = os.path.join(root, i)
                image_files.append(fix_unicode(file))
        
    gif_names = []
    images_set = []
    for parameter in parameters_to_read:
        if ':' in parameter:
            parameter = parameter.replace(':', '')
        parameter_files = []
        parameter_idx = []
        for filename in image_files:
            if parameter in filename:
                parameter_files.append(filename)
                name = os.path.normpath(filename).split(os.path.sep)[-1]
                parameter_idx.append(name[:name.index('_')])
        dat = zip(parameter_idx, parameter_files)
        gif_name = os.path.join(tomake_gif, f'{idx}_{parameter}_gif.gif')
        gif_name = fix_unicode(gif_name)
        gif_names.append(gif_name)
        parameter_files = sorted(dat, key = lambda tup: tup[0])
        parameter_files = [i[1] for i in parameter_files]
        with ThreadPool() as p:
            parameter_images = p.map(partial(imageio.imread, format = 'PNG'), parameter_files)
        images_set.append(parameter_images)
    _args = zip(gif_names, images_set)
    args = []
    for i, j in _args:
        args.append((i, j))
    with ThreadPool() as p:
        p.starmap(partial(imageio.mimsave, fps = 3, loop = 0), args)
        