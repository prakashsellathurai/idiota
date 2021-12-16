#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
base module for idiota 
"""
__author__ = "prakashsellathurai"
__copyright__ = "Copyright 2021"
__version__ = "1.0.1"
__email__ = "prakashsellathurai@gmail.com"

import itertools
import operator
import os
import string
from collections import deque, namedtuple

from . import data
from . import diff


def init():
    """
    Initialize a new repo
    """
    data.init()
    data.update_ref('HEAD', data.RefValue(
        symbolic=True, value='refs/heads/master'))


def write_tree():
    """
    Write the current working tree to the index
    """
    # Index is flat, we need it as a tree of dicts
    index_as_tree = {}
    with data.get_index() as index:
        for path, oid in index.items():
            path = path.split('/')
            dirpath, filename = path[:-1], path[-1]

            current = index_as_tree
            # Find the dict for the directory of this file
            for dirname in dirpath:
                current = current.setdefault(dirname, {})
            current[filename] = oid

    def write_tree_recursive(tree_dict):
        # Write the tree to the object store
        entries = []
        for name, value in tree_dict.items():
            if type(value) is dict:
                type_ = 'tree'
                oid = write_tree_recursive(value)
            else:
                type_ = 'blob'
                oid = value
            entries.append((name, oid, type_))

        tree = ''.join(f'{type_} {oid} {name}\n'
                       for name, oid, type_
                       in sorted(entries))
        return data.hash_object(tree.encode(), 'tree')

    return write_tree_recursive(index_as_tree)


def _iter_tree_entries(oid):
    """
    Iterate over the entries in a tree

    Args:
        oid: The oid of the tree
    Yields:
        Tuple of (type, oid, name)
    """
    if not oid:
        return
    tree = data.get_object(oid, 'tree')
    for entry in tree.decode().splitlines():
        type_, oid, name = entry.split(' ', 2)
        yield type_, oid, name


def get_tree(oid, base_path=''):
    """
     Get a tree as a dictionary of path -> oid
    
    args:
        oid: The oid of the tree
        base_path: The path to prepend to the tree entries
         default: ''
         
    returns:
        A dictionary of path -> oid
    """
    result = {}
    for type_, oid, name in _iter_tree_entries(oid):
        assert '/' not in name
        assert name not in ('..', '.')
        path = base_path + name
        if type_ == 'blob':
            result[path] = oid
        elif type_ == 'tree':
            result.update(get_tree(oid, f'{path}/'))
        else:
            assert False, f'Unknown tree entry {type_}'
    return result


def get_working_tree():
    """
    Get the current working tree as a dictionary of path -> oid
    
    args:
        None

    Returns:
        A dictionary of path -> oids
    """
    result = {}
    for root, _, filenames in os.walk('.'):
        for filename in filenames:
            path = os.path.relpath(f'{root}/{filename}')
            if is_ignored(path) or not os.path.isfile(path):
                continue
            with open(path, 'rb') as f:
                result[path] = data.hash_object(f.read())
    return result


def get_index_tree():
    """
       function to get the index tree

    Returns:
        A dictionary of path -> oid
    """
    with data.get_index() as index:
        return index


def _empty_current_directory():
    """ Empty the current directory """
    for root, _, filenames in os.walk('.'):
        for filename in filenames:
            path = os.path.relpath(f'{root}/{filename}')
            if is_ignored(path) or not os.path.isfile(path):
                continue
            os.remove(path)


def read_tree(tree_oid, update_working=False):
    """ Read a tree into the working directory 

    Args:
        tree_oid (str): The oid of the tree to read
        update_working (bool, optional): Whether to update the working directory Defaults to False.
    """
    with data.get_index() as index:
        index.clear()
        index.update(get_tree(tree_oid))

        if update_working:
            _checkout_index(index)


def read_tree_merged(t_base, t_HEAD, t_other, update_working=False):
    """ Read a tree into the working directory
    
    args:
        t_base (str): The oid of the base tree
        t_HEAD (str): The oid of the HEAD tree
        t_other (str): The oid of the other tree
        update_working (bool, optional): Whether to update the working directory Defaults to False.
    """
    with data.get_index() as index:
        index.clear()
        index.update(diff.merge_trees(
            get_tree(t_base),
            get_tree(t_HEAD),
            get_tree(t_other)
        ))

        if update_working:
            _checkout_index(index)


def _checkout_index(index):
    """
    Checkout the index into the current directory
    
    steps:
        1. Empty the current directory
        2. Write the index to the current directory


    args:
        index (dict): The index to checkout
        
    returns:
        None
    """
    _empty_current_directory()
    for path, oid in index.items():
        os.makedirs(os.path.dirname(f'./{path}'), exist_ok=True)
        with open(path, 'wb') as f:
            f.write(data.get_object(oid, 'blob'))


def commit(message):
    """
    Commit the current working tree
    
    steps:
        1. Write the current working tree to the index
        2. Write the index to the object store
        3. Write the commit to the object store
        4. Update the HEAD ref to point to the new commit
        5. return the oid of the new commit
    args:
        message (str): The commit message
        
    returns:
        The oid of the commit
    """
    commit = f'tree {write_tree ()}\n'

    HEAD = data.get_ref('HEAD').value

    if HEAD:
        commit += f'parent {HEAD}\n'
    MERGE_HEAD = data.get_ref('MERGE_HEAD').value
    if MERGE_HEAD:
        commit += f'parent {MERGE_HEAD}\n'
        data.delete_ref('MERGE_HEAD', deref=False)

    commit += '\n'
    commit += f'{message}\n'

    oid = data.hash_object(commit.encode(), 'commit')

    data.update_ref('HEAD', data.RefValue(symbolic=False, value=oid))

    return oid


def checkout(name):
    """checkout the branch with name

    steps:
        1. Get the oid of the branch
        2. Read the tree with the oid
        3. Write the tree to the index
        
    Args:
        name (str): The name of the branch to checkout
    """
    oid = get_oid(name)
    commit = get_commit(oid)
    read_tree(commit.tree, update_working=True)

    if is_branch(name):
        HEAD = data.RefValue(symbolic=True, value=f'refs/heads/{name}')
    else:
        HEAD = data.RefValue(symbolic=False, value=oid)

    data.update_ref('HEAD', HEAD, deref=False)


def reset(oid):
    """ Resets the commit to the given oid

    Args:
        oid (str): The oid to reset to
    """
    data.update_ref('HEAD', data.RefValue(symbolic=False, value=oid))


def merge(other):
    """
    Merge the other branch into the current branch

    steps:
        1. Get the oid of the other branch
        2. Read the tree with the oid
        3. Write the tree to the index
        4. Write the index to the object store
        5. Write the commit to the object store
        6. Update the HEAD ref to point to the new commit
        7. return the oid of the new commit
        
    Args:
        other (str): The name of the branch to merge
    
    returns:
        None
    """
    HEAD = data.get_ref('HEAD').value
    assert HEAD
    merge_base = get_merge_base(other, HEAD)
    c_other = get_commit(other)

    # Handle fast-forward merge
    if merge_base == HEAD:
        read_tree(c_other.tree, update_working=True)
        data.update_ref('HEAD',
                        data.RefValue(symbolic=False, value=other))
        print('Fast-forward merge, no need to commit')
        return

    data.update_ref('MERGE_HEAD', data.RefValue(symbolic=False, value=other))

    c_base = get_commit(merge_base)
    c_HEAD = get_commit(HEAD)
    read_tree_merged(c_base.tree, c_HEAD.tree,
                     c_other.tree, update_working=True)
    print('Merged in working tree\nPlease commit')


def get_merge_base(oid1, oid2):
    """
    Get the merge base of the two commits

    Args:
        oid1 (str): The oid of the first commit
        oid2 (str): The oid of the second commit

    steps:
        1. Get the commit with the oid1
        2. Get the commit with the oid2
        3. Get the common ancestor of the two commits
        4. return the oid of the common ancestor
    Returns:
        The oid of the merge base
    """
    parents1 = list(iter_commits_and_parents({oid1}))

    for oid in iter_commits_and_parents({oid2}):
        if oid in parents1:
            return oid


def create_tag(name, oid):
    """
    Create a tag with the given name and oid
    
    Args:
        name (str): The name of the tag
        oid (str): The oid of the commit to tag
    
    Returns:
        None
    """
    data.update_ref(f'refs/tags/{name}',
                    data.RefValue(symbolic=False, value=oid))


def create_branch(name, oid):
    """
    create a branch with the given name and oid
    
    Args:
        name (str): The name of the branch
        oid (str): The oid of the commit to branch from
    
    Returns:
        None
    """
    data.update_ref(f'refs/heads/{name}',
                    data.RefValue(symbolic=False, value=oid))


def iter_branch_names():
    for refname, _ in data.iter_refs('refs/heads/'):
        yield os.path.relpath(refname, 'refs/heads/')


def is_branch(branch):
    return data.get_ref(f'refs/heads/{branch}').value is not None


def get_branch_name():
    HEAD = data.get_ref('HEAD', deref=False)
    if not HEAD.symbolic:
        return None
    HEAD = HEAD.value
    assert HEAD.startswith('refs/heads/')
    return os.path.relpath(HEAD, 'refs/heads')


Commit = namedtuple('Commit', ['tree', 'parents', 'message'])


def get_commit(oid):
    parents = []

    commit = data.get_object(oid, 'commit').decode()
    lines = iter(commit.splitlines())
    for line in itertools.takewhile(operator.truth, lines):
        key, value = line.split(' ', 1)
        if key == 'tree':
            tree = value
        elif key == 'parent':
            parents = []
        else:
            assert False, f'Unknown field {key}'

    message = '\n'.join(lines)
    return Commit(tree=tree, parents=parents, message=message)


def iter_commits_and_parents(oids):
    oids = deque(oids)
    visited = set()

    while oids:
        oid = oids.popleft()
        if not oid or oid in visited:
            continue
        visited.add(oid)
        yield oid

        commit = get_commit(oid)
        # Return first parent next
        oids.extendleft(commit.parents[:1])
        # Return other parents later
        oids.extend(commit.parents[1:])


def iter_objects_in_commits(oids):
    # N.B. Must yield the oid before acccessing it (to allow caller to fetch it
    # if needed)

    visited = set()

    def iter_objects_in_tree(oid):
        visited.add(oid)
        yield oid
        for type_, oid, _ in _iter_tree_entries(oid):
            if oid not in visited:
                if type_ == 'tree':
                    yield from iter_objects_in_tree(oid)
                else:
                    visited.add(oid)
                    yield oid

    for oid in iter_commits_and_parents(oids):
        yield oid
        commit = get_commit(oid)
        if commit.tree not in visited:
            yield from iter_objects_in_tree(commit.tree)


def get_oid(name):
    if name == '@':
        name = 'HEAD'

    refs_to_try = [
        f'{name}',
        f'refs/{name}',
        f'refs/tags/{name}',
        f'refs/heads/{name}',
    ]
    for ref in refs_to_try:
        if data.get_ref(ref, deref=False).value:
            return data.get_ref(ref).value

    # Name is SHA1
    is_hex = all(c in string.hexdigits for c in name)
    if len(name) == 40 and is_hex:
        return name

    assert False, f'Unknown name {name}'


def add(filenames):

    def add_file(filename):
        # Normalize path
        filename = os.path.relpath(filename)
        with open(filename, 'rb') as f:
            oid = data.hash_object(f.read())
        index[filename] = oid

    def add_directory(dirname):
        for root, _, filenames in os.walk(dirname):
            for filename in filenames:
                # Normalize path
                path = os.path.relpath(f'{root}/{filename}')
                if is_ignored(path) or not os.path.isfile(path):
                    continue
                add_file(path)

    with data.get_index() as index:
        for name in filenames:
            if os.path.isfile(name):
                add_file(name)
            elif os.path.isdir(name):
                add_directory(name)


def is_ignored(path):
    return '.idiota' in path.split('/')
