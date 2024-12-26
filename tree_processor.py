from weight_calculator import calculate_dynamic_weight
from lsh_signature import compute_node_signature

def process_tree(root, num_perm=128):
    stack = [(root, None)]
    max_depth = 0
    max_branching_factor = 0
    
    while stack:
        node, parent = stack.pop()
        if parent:
            node.depth = parent.depth + 1
        max_depth = max(max_depth, node.depth)
        max_branching_factor = max(max_branching_factor, len(node.children))
        
        for child in node.children:
            stack.append((child, node))
    
    root.max_depth = max_depth
    root.max_branching_factor = max_branching_factor
    
    for node in traverse_tree(root):
        node.weight = calculate_dynamic_weight(node, root)
        node.signature = compute_node_signature(node, num_perm)

def traverse_tree(root):
    stack = [root]
    while stack:
        node = stack.pop()
        yield node
        stack.extend(node.children)
