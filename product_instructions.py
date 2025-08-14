from copy import copy, deepcopy
from file_utils import object_to_dict
from collections import defaultdict, deque

class OperationNodeClean():
    def __init__(self, node_type, operation_name='', display_pos=None, node_uid=None, components={}, capabilities=[], tools={},
                 processing_time_value=0.0, processing_time_unit='', output_name=''):
        self.node_type = node_type
        self.operation_name = operation_name
        self.display_pos = display_pos
        self.node_uid = node_uid
        # Operation requirements and outputs
        self.components = components  # key: component name, value: quantity
        self.capabilities = capabilities  # list of capabilities that are required from resources that execute this operation
        self.tools = tools  # dictionary of required tools with requirements and effects
        self.processing_time_value = processing_time_value  # how long the operation takes
        self.processing_time_unit = processing_time_unit
        self.output_name = output_name  # name of the part or subassembly that leaves the operation after processing

    def to_dict(self):
        return {
            "node_type": self.node_type,
            "operation_name": self.operation_name,
            "display_pos": object_to_dict((self.display_pos.x(), self.display_pos.y())),
            "node_uid": self.node_uid,
            "components": object_to_dict(self.components),
            "capabilities": object_to_dict(self.capabilities),
            "tools": object_to_dict(self.tools),
            "processing_time_value": self.processing_time_value,
            "processing_time_unit": self.processing_time_unit,
            "output_name": self.output_name
        }

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
    
    def clean_operation_node(self, op):
        return OperationNodeClean(node_type=op.node_type,
                                    operation_name=op.operation_name,
                                    display_pos=op.display_pos,
                                    node_uid=op.node_uid,
                                    components=op.components,
                                    capabilities=op.capabilities,
                                    tools=op.tools,
                                    processing_time_value=op.processing_time_value,
                                    processing_time_unit=op.processing_time_unit,
                                    output_name=op.output_name)
    
    def clean_from_qt(self):
        '''
        Replaces every instance of an OperationNode by OperationNodeClean in ProductPalette,
        removing any references to PyQT objects that are not serializable by Ray library for MuZero.
        '''
        palette_replacement = {}
        for product_id, precedence_list in self.product_palette.items():
            # Product is a list of "precedences" stored as tuples (start_node, end_node)
            new_precedence_list = []
            # Use node_uid as identifier to recreate the same structure as in original precedence list
            temp_clean_op_dict = {}
            for precedence in precedence_list:
                source = precedence[0]
                target = precedence[1]
                if source.node_uid not in temp_clean_op_dict.keys():
                    source = self.clean_operation_node(source)
                    temp_clean_op_dict.update({source.node_uid: source})
                else:
                    source = temp_clean_op_dict[source.node_uid]
                if target.node_uid not in temp_clean_op_dict.keys():
                    target = self.clean_operation_node(target)
                    temp_clean_op_dict.update({target.node_uid: target})
                else:
                    target = temp_clean_op_dict[target.node_uid]
                new_precedence_list.append((source, target))
            palette_replacement.update({product_id: new_precedence_list})
        self.product_palette = palette_replacement

    def get_product_operations(self):
        '''Returns a dictionary that tells what operations constitute a product by a given id.'''
        product_operations = {}
        for product_id, precedence_list in self.product_palette.items():
            # Get all predecessor operations
            predecessors = [precedence[0] for precedence in precedence_list]
            # Get all successor operations
            successors = [precedence[1] for precedence in precedence_list]
            # Get the union of these two sets
            all_operations = list(set(predecessors).union(successors))

            # Important for Ray serialization: strip OperationNode objects of all Qt functions!
            all_clean_operations = []
            for op in all_operations:
                if not isinstance(op, OperationNodeClean):
                    op_clean = self.clean_operation_node(op)
                    all_clean_operations.append(op_clean)
                else:
                    all_clean_operations.append(op)

            product_operations.update({product_id: all_clean_operations})

        return product_operations
    

    def get_predecessor_ids(self, operation, product):
        '''Returns a list of predecessor ids of the operation in the product.'''
        predecessor_ids = [connection[0].operation_name for connection in product if connection[1].node_uid == operation.node_uid]
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
