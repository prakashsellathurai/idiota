import os
import hashlib

GIT_DIR = '.idiota'


def init ():
    os.makedirs (GIT_DIR)
    os.makedirs (f'{GIT_DIR}/objects')


def hash_object (data, type_='blob'):
    obj = type_.encode () + b'\x00' + data
    oid = hashlib.sha1 (obj).hexdigest ()
    with open (f'{GIT_DIR}/objects/{oid}', 'wb') as out:
        out.write (obj)
    return oid

def get_object (oid, expected='blob'):
    with open (f'{GIT_DIR}/objects/{oid}', 'rb') as f:
        obj = f.read ()

    first_null = obj.index (b'\x00')
    type_ = obj[:first_null].decode ()
    content = obj[first_null + 1:]

    if expected is not None:
        assert type_ == expected, f'Expected {expected}, got {type_}'
    return content