import os
import hashlib
from collections import defaultdict
import argparse
import json
from typing import Dict, List, Tuple, Optional
import matplotlib.pyplot as plt
import networkx as nx
import time
import concurrent.futures
import difflib

# 文件节点
class FileNode:
    def __init__(self, name: str, is_dir: bool, size: int = 0):
        self.name = name
        self.is_dir = is_dir
        self.children: List['FileNode'] = []
        self.content_hash: Optional[str] = None
        self.size = size

    def add_child(self, child: 'FileNode'):
        self.children.append(child)

    def calculate_hash(self) -> str:
        if not self.is_dir:
            return self.content_hash or ''
        child_hashes = [child.calculate_hash() for child in self.children]
        return hashlib.md5(''.join(child_hashes).encode()).hexdigest()

    def to_dict(self) -> Dict:
        return {
            'name': self.name,
            'is_dir': self.is_dir,
            'size': self.size,
            'content_hash': self.content_hash,
            'children': [child.to_dict() for child in self.children]
        }

def scan_directory(path: str) -> FileNode:
    root = FileNode(os.path.basename(path), True)
    for item in os.scandir(path):
        if item.is_dir():
            child = scan_directory(item.path)
        else:
            child = FileNode(item.name, False, item.stat().st_size)
            with open(item.path, 'rb') as f:
                content = f.read()
                child.content_hash = hashlib.md5(content).hexdigest()
        root.add_child(child)
    return root

def compare_trees(tree1: FileNode, tree2: FileNode) -> Tuple[float, List[str]]:
    def get_node_info(node: FileNode) -> List[Tuple[str, bool, int, str]]:
        result = [(node.name, node.is_dir, node.size, node.content_hash)]
        for child in node.children:
            result.extend(get_node_info(child))
        return result

    info1 = set(get_node_info(tree1))
    info2 = set(get_node_info(tree2))
    
    intersection = info1.intersection(info2)
    union = info1.union(info2)
    
    similarity = len(intersection) / len(union) if union else 0
    
    differences = []
    for item in union - intersection:
        if item in info1:
            differences.append(f"Only in {tree1.name}: {item[0]}")
        else:
            differences.append(f"Only in {tree2.name}: {item[0]}")
    
    return similarity, differences

def visualize_diff(tree1: FileNode, tree2: FileNode, similarity: float):
    G = nx.Graph()
    
    def add_nodes(node: FileNode, prefix: str, color: str):
        G.add_node(f"{prefix}_{node.name}", color=color, size=node.size)
        for child in node.children:
            G.add_node(f"{prefix}_{child.name}", color=color, size=child.size)
            G.add_edge(f"{prefix}_{node.name}", f"{prefix}_{child.name}")
            add_nodes(child, prefix, color)
    
    add_nodes(tree1, "A", "lightblue")
    add_nodes(tree2, "B", "lightgreen")
    
    pos = nx.spring_layout(G)
        colors = [G.nodes[node]['color'] for node in G.nodes()]
    sizes = [G.nodes[node]['size'] / 1000 + 100 for node in G.nodes()]  # 根据文件大小调整节点大小
    
    plt.figure(figsize=(16, 12))
    nx.draw(G, pos, node_color=colors, node_size=sizes, with_labels=True, font_size=8)
    plt.title(f"Directory Structure Comparison (Similarity: {similarity:.2f})")
    plt.axis('off')
    plt.tight_layout()
    plt.savefig("tree_diff_visualization.png", dpi=300, bbox_inches='tight')
    plt.close()

def calculate_file_hash(file_path: str) -> str:
    with open(file_path, 'rb') as f:
        content = f.read()
        return hashlib.md5(content).hexdigest()

def parallel_scan_directory(path: str) -> FileNode:
    root = FileNode(os.path.basename(path), True)
    
    def process_item(item):
        if item.is_dir():
            return scan_directory(item.path)
        else:
            child = FileNode(item.name, False, item.stat().st_size)
            child.content_hash = calculate_file_hash(item.path)
            return child
    
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = [executor.submit(process_item, item) for item in os.scandir(path)]
        for future in concurrent.futures.as_completed(futures):
            root.add_child(future.result())
    
    return root

def generate_diff_report(tree1: FileNode, tree2: FileNode, differences: List[str]) -> str:
    report = f"Comparison Report: {tree1.name} vs {tree2.name}\n"
    report += "=" * 50 + "\n\n"
    
    report += "Summary:\n"
    report += f"Total files in {tree1.name}: {len(get_node_info(tree1))}\n"
    report += f"Total files in {tree2.name}: {len(get_node_info(tree2))}\n"
    report += f"Number of differences: {len(differences)}\n\n"
    
    report += "Detailed Differences:\n"
    for diff in differences:
        report += f"- {diff}\n"
    
    return report

def get_node_info(node: FileNode) -> List[Tuple[str, bool, int, str]]:
    result = [(node.name, node.is_dir, node.size, node.content_hash)]
    for child in node.children:
        result.extend(get_node_info(child))
    return result

def find_similar_files(tree1: FileNode, tree2: FileNode) -> List[Tuple[str, str, float]]:
    files1 = [node for node in get_node_info(tree1) if not node[1]]  # 只比较文件，不比较目录
    files2 = [node for node in get_node_info(tree2) if not node[1]]
    
    similar_files = []
    for file1 in files1:
        for file2 in files2:
            if file1[0] != file2[0]:  # 名称不同的文件
                similarity = difflib.SequenceMatcher(None, file1[3], file2[3]).ratio()
                if similarity > 0.8:  # 相似度阈值
                    similar_files.append((file1[0], file2[0], similarity))
    
    return similar_files

def main():
    parser = argparse.ArgumentParser(description="Compare two directory structures")
    parser.add_argument("dir1", help="Path to the first directory")
    parser.add_argument("dir2", help="Path to the second directory")
    parser.add_argument("--output", "-o", default="comparison_result.json", help="Output file for comparison results")
    parser.add_argument("--report", "-r", default="diff_report.txt", help="Output file for difference report")
    parser.add_argument("--parallel", "-p", action="store_true", help="Use parallel processing for directory scanning")
    args = parser.parse_args()

    start_time = time.time()

    print(f"Scanning directory: {args.dir1}")
    tree1 = parallel_scan_directory(args.dir1) if args.parallel else scan_directory(args.dir1)
    print(f"Scanning directory: {args.dir2}")
    tree2 = parallel_scan_directory(args.dir2) if args.parallel else scan_directory(args.dir2)

    print("Comparing directory structures...")
    similarity, differences = compare_trees(tree1, tree2)

    print(f"Similarity between the two directories: {similarity:.2f}")

    result = {
        "directory1": args.dir1,
        "directory2": args.dir2,
        "similarity": similarity,
        "tree1_hash": tree1.calculate_hash(),
        "tree2_hash": tree2.calculate_hash(),
        "differences": differences
    }

    with open(args.output, 'w') as f:
        json.dump(result, f, indent=2)

    print(f"Comparison result saved to {args.output}")

    print("Generating difference report...")
    report = generate_diff_report(tree1, tree2, differences)
    with open(args.report, 'w') as f:
        f.write(report)
    print(f"Difference report saved to {args.report}")

    print("Finding similar files...")
    similar_files = find_similar_files(tree1, tree2)
    if similar_files:
        print("Similar files found:")
        for file1, file2, sim in similar_files:
            print(f"  {file1} <-> {file2} (Similarity: {sim:.2f})")
    else:
        print("No similar files found.")

    print("Generating visualization...")
    visualize_diff(tree1, tree2, similarity)
    print("Visualization saved as tree_diff_visualization.png")

    end_time = time.time()
    print(f"Total execution time: {end_time - start_time:.2f} seconds")

def calculate_directory_stats(node: FileNode) -> Dict[str, int]:
    stats = defaultdict(int)
    
    def traverse(n: FileNode):
        if n.is_dir:
            stats['directories'] += 1
        else:
            stats['files'] += 1
            stats['total_size'] += n.size
            ext = os.path.splitext(n.name)[1].lower()
            stats[f'files_{ext}'] += 1
        
        for child in n.children:
            traverse(child)
    
    traverse(node)
    return dict(stats)

def generate_tree_structure(node: FileNode, indent: str = "") -> str:
    result = f"{indent}{node.name}\n"
    for child in sorted(node.children, key=lambda x: (x.is_dir, x.name), reverse=True):
        if child.is_dir:
            result += generate_tree_structure(child, indent + "  ")
        else:
            result += f"{indent}  {child.name}\n"
    return result

if __name__ == "__main__":
    main()
