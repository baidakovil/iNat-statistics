import os
import operator
from datetime import datetime
from datetime import timedelta
import piexif


class CFG:
    
    LIBRARYPATH_DEFAULT = '/media/eva/DATA/Naturalist/'
    JPGFOLDER_DEFAULT = 'Aug 31'
    MAXDELTA = timedelta(seconds=2)
    MINSTACKLEN = 5
    MAXSTACKLEN = 10


def read_jpg(LIBRARYPATH_DEFAULT, JPGFOLDER_DEFAULT):

    # function to read names and dates from jpg files in source folder
    # also define where files are lie

    # -- for debugging --
    LIBRARYPATH = ''
    JPGFOLDER = ''
    # -- for debugging --

    # LIBRARYPATH = input(f'Enter library path or default path will be used: "{CFG.LIBRARYPATH_DEFAULT}"')
    if LIBRARYPATH == '':
        LIBRARYPATH = CFG.LIBRARYPATH_DEFAULT

    # JPGFOLDER = input(f'Enter dir name or default dir name will be used: "{CFG.JPGFOLDER_DEFAULT}"')
    if JPGFOLDER == '':
        JPGFOLDER = CFG.JPGFOLDER_DEFAULT

    JPGPATH = os.path.join(LIBRARYPATH, JPGFOLDER)

    names = []
    format = '%Y:%m:%d %H:%M:%S'

    print(f'\nRead jpg...', end='')

    for file in os.listdir(JPGPATH):
        if file.lower().endswith('.jpg'):
            names.append(file)

    names = sorted(names)

    if len(names) == 0:
        print(f'\nNo JPG files in folder!')
    else:
        print(f'ok.\nGot {len(names)} JPG in folder')

    dates_bytes = [piexif.load(os.path.join(JPGPATH, name))['0th'][306]
                   for name in names]

    dates = sorted([datetime.strptime(str(date)[2:-1], format) for date in dates_bytes])

    print(
        f'Got {len(dates)} timestamps in JPGs\nFROM: {dates[0]} \nTO  : {dates[-1]}\n')

    return dates, names, JPGPATH


def get_stacks(dates, names):

    # function to create list of stacks (list of lists)
    # and print statistics on size and count of stacks
    
    stack_stat = dict()
    stacks = []
    stack = []
    stack.append(dates[0])

    def done_stack(stacks, stack_stat, stack):

        # function to send new jpg-filenames-list (stack) to list of stacks
        # and refresh statistics on stack lenghts
        if len(stack) >= CFG.MINSTACKLEN:
            stacks.append(stack)
            stack_stat[len(stack)] = stack_stat.get(len(stack), 0) + 1
            if len(stack) > CFG.MAXSTACKLEN:
                print(f'Strange long stack ({len(stack)}) elements. From {stack[0]} to {stack[-1]}')
        else:
            pass

        return stacks, stack_stat

    for i in range(1, len(dates)-1):

        delta = dates[i] - dates[i-1]

        if delta <= CFG.MAXDELTA:
        # DATES NEAR EACH OTHER
        # ADD NAME TO STACK
            stack.append(names[i])

            if i == (len(dates)-1):
            #FINISH CYCLE WITH ADD STACK TO STACKS
                stacks, stack_stat = done_stack(stacks, stack_stat, stack)
                del stack
        else:
        # DATES FAR FROM EACH OTHER
        # ADD STACK TO STACKS 
            stacks, stack_stat = done_stack(stacks, stack_stat, stack)

            if i == (len(dates)-1):
            # FINISH CYCLE
                del stack
            else:
            # START NEW STACK
                stack = [names[i]]

    for stacksize, stackcount in sorted(stack_stat.items(), key=operator.itemgetter(0)):
        spacer = ' ' if stacksize < 10 else ''
        print(f'Stack size {spacer}{stacksize} files: {stackcount} stacks')

    return stacks


def move_stacks(stacks, JPGPATH):

    # function to create 'fs' folder
    # and all the stack-folders
    # and move jpg-files-list (stacks) to their folders

    folder_count = 0
    file_count = 0

    os.mkdir(os.path.join(JPGPATH, 'fs'))
    print(f'\nFolder "fs" created')

    print('Start moving files...', end='')

    for stack in stacks:

        stack_dirname = stack[0][:-4]+'_to_' + stack[-1][:-4]
        stack_path = os.path.join(JPGPATH, 'fs', stack_dirname)
        os.mkdir(stack_path)
        folder_count += 1

        for name in stack:

            src = os.path.join(JPGPATH, name)
            dst = os.path.join(stack_path, name)
            os.rename(src, dst)
            file_count += 1
        
    print(f'Ok:\n{folder_count} folders created\n{file_count} files moved')


def main():
    
    # main process
    print(f'START\n')

    dates, names, JPGPATH = read_jpg(CFG.LIBRARYPATH_DEFAULT, CFG.JPGFOLDER_DEFAULT)
    stacks = get_stacks(dates, names)
    move_stacks(stacks, JPGPATH)

    print(f'\nFINISH')

main()