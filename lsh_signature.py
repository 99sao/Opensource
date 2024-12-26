from datasketch import MinHash

def compute_node_signature(node, num_perm=128):
    minhash = MinHash(num_perm=num_perm)
    minhash.update(node.name.encode('utf-8'))
    for child in node.children:
        minhash.update(child.name.encode('utf-8'))
    return minhash
