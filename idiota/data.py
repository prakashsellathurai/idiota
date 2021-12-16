#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
    Idiota object types
    
    tree - A tree (directory listing) object that represents the directory structure in a tree object.
    commit(ref) - A  object that represents the changes in a single commit.
    blob - A blob object that represents a file or a piece of data.  
    parent - A  object that represents the ancestor to the commit in the DaG.
    tag  - A  object that represents a meta info.
"""

__author__ = "prakashsellathurai"
__copyright__ = "Copyright 2021"
__version__ = "1.0.1"
__email__ = "prakashsellathurai@gmail.com"

import os
import hashlib
import shutil
import json

from collections import namedtuple
from contextlib import contextmanager


GIT_DIR = None
RefValue = namedtuple('RefValue', ['symbolic', 'value'])

@contextmanager
def change_git_dir(new_dir) -> None:
    """
    Change the current git directory
    
    Args:   
        new_dir (str): new git directory
        
    Yields:
        str: old git directory
    """
    global GIT_DIR
    old_dir = GIT_DIR
    GIT_DIR = f'{new_dir}/.idiota'
    yield
    GIT_DIR = old_dir


def init() -> None:
    """
    Create .idiota directory
    
    Returns:
        None
    """
    os.makedirs(GIT_DIR, exist_ok=True)
    os.makedirs(f'{GIT_DIR}/objects')





def update_ref(ref, value, deref: bool=True) -> None:
    """ Update a ref
    
    Args:   
        ref (str): ref name
        value (str): ref value
        deref (bool): dereference symbolic refs
        
    Returns:
        None
    """
    # TODO: check if ref exists
    # TODO: check if value is valid
    # TODO: check if ref is symbolic
    
    
    ref = _get_ref_internal(ref, deref)[0]

    assert value.value
    if value.symbolic:
        value = f'ref: {value.value}'
    else:
        value = value.value

    ref_path = f'{GIT_DIR}/{ref}'
    os.makedirs(os.path.dirname(ref_path), exist_ok=True)
    with open(ref_path, 'w') as f:
        f.write(value)


def get_ref(ref, deref=True) -> RefValue:
    """ Get a ref value

    Args:
        ref (str): ref name
        deref (bool): dereference symbolic refs
    Returns:
        RefValue(str): ref value
    """
    return _get_ref_internal(ref, deref)[1]


def delete_ref(ref, deref=True)->None:
    """ Delete a ref"""
    ref = _get_ref_internal(ref, deref)[0]
    os.remove(f'{GIT_DIR}/{ref}')


def _get_ref_internal(ref, deref) -> RefValue:
    """ Get a ref value
    
    Args:
        ref (str): ref name
        deref (bool): dereference symbolic refs
    
    Returns:
        RefValue (str): ref value
    """
    ref_path = f'{GIT_DIR}/{ref}'
    value = None
    if os.path.isfile(ref_path):
        with open(ref_path) as f:
            value = f.read().strip()

    symbolic = bool(value) and value.startswith('ref:')
    if symbolic:
        value = value.split(':', 1)[1].strip()
        if deref:
            return _get_ref_internal(value, deref=True)

    return ref, RefValue(symbolic=symbolic, value=value)


def iter_refs(prefix='', deref=True):
    """ Iterate over refs
    
    Args:
        prefix (str): ref prefix
        deref (bool): dereference symbolic refs
    
    Returns:
        Iterator[Tup(str, RefValue)]: ref name and ref value
    """
    refs = ['HEAD', 'MERGE_HEAD']
    for root, _, filenames in os.walk(f'{GIT_DIR}/refs/'):
        root = os.path.relpath(root, GIT_DIR)
        refs.extend(f'{root}/{name}' for name in filenames)

    for refname in refs:
        if not refname.startswith(prefix):
            continue
        ref = get_ref(refname, deref=deref)
        if ref.value:
            yield refname, ref


@contextmanager
def get_index():
    """ Get index

    Yields:
        Index: index
    """
    index = {}
    if os.path.isfile(f'{GIT_DIR}/index'):
        with open(f'{GIT_DIR}/index') as f:
            index = json.load(f)

    yield index

    with open(f'{GIT_DIR}/index', 'w') as f:
        json.dump(index, f)


def hash_object(data: object, type_='blob')-> str:
    """
    Hash an object
    
    uses: Sha1 algorithm
    
    Args:
        data (bytes): object data
        
    Returns:
        str: object id
    """
    obj = type_.encode() + b'\x00' + data
    oid = hashlib.sha1(obj).hexdigest()
    with open(f'{GIT_DIR}/objects/{oid}', 'wb') as out:
        out.write(obj)
    return oid


def get_object(oid: str, expected='blob')-> object:
    """
    get an object
    
    Args:
        oid (str): object id
        
    Returns:
        bytes: object data
    """

    with open(f'{GIT_DIR}/objects/{oid}', 'rb') as f:
        obj = f.read()

    first_null = obj.index(b'\x00')
    type_ = obj[:first_null].decode()
    content = obj[first_null + 1:]

    if expected is not None:
        assert type_ == expected, f'Expected {expected}, got {type_}'
    return content


def object_exists(oid: bool)-> bool:
    """ 
    checks if object of given id exists in the repository
    
    Args:
        oid (str): object id
    
    Returns:
        bool: True if object exists
    """
    return os.path.isfile(f'{GIT_DIR}/objects/{oid}')


def fetch_object_if_missing(oid, remote_git_dir):
    """
    fetch object from remote repository if it is not present in local repository
    
    Args:
        oid (str): object id
        remote_git_dir (str): remote git directory
        
    Returns:
        None
    """
    if object_exists(oid):
        return
    remote_git_dir += '/.ugit'
    shutil.copy(f'{remote_git_dir}/objects/{oid}',
                f'{GIT_DIR}/objects/{oid}')


def push_object(oid, remote_git_dir):
    """
    push object to remote repository

    Args:
        oid (str): object id
        remote_git_dir (str): remote git directory
        
    Returns:
        None
    """
    remote_git_dir += '/.ugit'
    shutil.copy(f'{GIT_DIR}/objects/{oid}',
                f'{remote_git_dir}/objects/{oid}')
