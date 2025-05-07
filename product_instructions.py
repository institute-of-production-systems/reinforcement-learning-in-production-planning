from copy import copy, deepcopy
from file_utils import object_to_dict
from collections import defaultdict, deque

class ProductPalette():
    '''
    The product palette of a company is stored as a dictionary with
    key = product ID and value = list of connections between operation nodes.
    The production graph for each product is thus stored as a connection list.
    '''
    def __init__(self, product_palette=dict()):
        self.product_palette = product_palette  # dict {'product_id': [connections]}


    def to_dict(self):
        return {
            "product_palette": object_to_dict(self.product_palette)
        }


    def add_product_graph(self, product_id, connection_list):
        print(f"--> Updated product graph for product {product_id}")
        self.product_palette.update({copy(product_id): copy(connection_list)})
        #print(self.product_palette)


    def get_raw_material_names(self):
        '''Gets components of operation nodes without incoming edges in the product graph.'''

        # A better idea would be actually to see what components appear in operation inputs but nowhere in operation outputs!

        # raw_material_names = []
        # for product in self.product_palette.values():
        #     # Get all predecessor operations
        #     predecessors = [connection[0] for connection in product]
        #     # Get all successor operations
        #     successors = [connection[1] for connection in product]
        #     # Get all operation nodes that are in predecessors list but not in successors list
        #     source_operations = list(set(predecessors).difference(successors))
        #     for source_operation in source_operations:
        #         for raw_material in source_operation.components.keys():
        #             raw_material_names.append(raw_material)

        raw_material_names = []
        product_operations = self.get_product_operations()
        input_components = []
        output_names = []
        for operation_node_list in product_operations.values():
            for operation_node in operation_node_list:
                for component in operation_node.components.keys():
                    input_components.append(component)
                output_names.append(operation_node.output_name)

        input_components = list(set(input_components))
        output_names = list(set(output_names))

        raw_material_names = list(set(input_components).difference(output_names))

        return raw_material_names
    

    def get_product_operations(self):
        '''Returns a dictionary that tells what operations constitute a product by a given id.'''
        product_operations = {}
        for product_id, product in self.product_palette.items():
            # Get all predecessor operations
            predecessors = [connection[0] for connection in product]
            # Get all successor operations
            successors = [connection[1] for connection in product]
            # Get the union of these two sets
            all_operations = list(set(predecessors).union(successors))
            product_operations.update({product_id: all_operations})
        return product_operations
    

    def get_predecessor_ids(self, operation, product):
        '''Returns a list of predecessor ids of the operation in the product.'''
        predecessor_ids = [connection[0].operation_name for connection in product if connection[1] == operation]
        return list(set(predecessor_ids))
    

    def critical_path_duration(self, edges, durations):
        """
        Computes the critical path duration of a precedence graph.

        :param edges: List of tuples (u, v) meaning operation u must precede v.
        :param durations: Dict {node: processing_duration} for each operation.
        :return: Critical path duration (longest path in DAG).
        """
        # Build adjacency list and compute in-degrees
        graph = defaultdict(list)
        in_degree = defaultdict(int)
        
        for u, v in edges:
            graph[u].append(v)
            in_degree[v] += 1
            if u not in in_degree:
                in_degree[u] = 0  # Ensure all nodes are in in_degree
        
        # Topological sorting (Kahn’s algorithm)
        topo_order = []
        queue = deque([node for node in in_degree if in_degree[node] == 0])
        
        longest_path = {node: durations[node] for node in in_degree}  # Start with node durations
        
        while queue:
            node = queue.popleft()
            topo_order.append(node)
            
            for neighbor in graph[node]:
                in_degree[neighbor] -= 1
                # Update longest path to the neighbor
                longest_path[neighbor] = max(longest_path[neighbor], longest_path[node] + durations[neighbor])
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
        
        # Critical path duration is the max value in longest_path
        return max(longest_path.values())
    
        # Example usage:
        edges = [(1, 2), (1, 3), (2, 4), (3, 4)]
        durations = {1: 3, 2: 2, 3: 4, 4: 5}  # Processing times of each node

        critical_duration = critical_path_duration(edges, durations)
