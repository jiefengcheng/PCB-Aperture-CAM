"""Use standard complete pages; bind genuine empty inventories explicitly."""
from src.t01_crop.paging import store_pages,read_pages


def put(store,rows,*,binding,kind):
    if rows:return store_pages(store,rows,binding=binding,kind=kind)
    return store.put_json('u03-empty-inventory',dict(binding=binding,kind=kind,total_records=0,pages=[]))


def get(store,ref,*,binding,kind,identity):
    if ref['artifact_id'].startswith('u03-empty-inventory:'):
        value=store.get_json(ref,kind='u03-empty-inventory')
        if value!=dict(binding=binding,kind=kind,total_records=0,pages=[]):raise ValueError('U03_EMPTY_INVENTORY_BINDING_CHANGED')
        return [],value
    return read_pages(store,ref,binding=binding,kind=kind,identity=identity)
