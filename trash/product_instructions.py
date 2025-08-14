from abc import ABC, abstractmethod

# Base class for all nodes
class OperationNode(ABC):
    def __init__(self, name, duration):
        self.name = name
        self.duration = duration  # time required for this operation
        self.predecessors = []  # nodes that must be completed before this node

    def add_predecessor(self, node):
        """Add a node as a prerequisite for this operation."""
        self.predecessors.append(node)

    @abstractmethod
    def execute(self):
        """Define behavior when this node is processed."""
        pass

# Assembly Node: Represents operations that bring components together
class AssemblyNode(OperationNode):
    def __init__(self, name, components, duration):
        super().__init__(name, duration)
        self.components = components  # List of components required for assembly
        self.required_manufacturing_graphs = []  # List of ManufacturingGraphs producing required components

    def add_required_manufacturing_graph(self, manufacturing_graph):
        """Add a manufacturing graph that must complete before this assembly can start."""
        if manufacturing_graph.output_id in self.components:
            self.required_manufacturing_graphs.append(manufacturing_graph)
        else:
            raise ValueError(f"Output ID of {manufacturing_graph} not in required components list")

    def check_preconditions(self):
        """Check if all required manufacturing graphs are completed."""
        return all(graph.is_completed() for graph in self.required_manufacturing_graphs)

    def execute(self):
        if self.check_preconditions():
            print(f"Executing assembly: {self.name} with components: {self.components}")
        else:
            print(f"Cannot execute assembly {self.name}. Not all required components are completed.")

# Non-Additive Activity Node: Time-consuming, non-additive activities
class NonAdditiveActivityNode(OperationNode):
    def __init__(self, name, duration):
        super().__init__(name, duration)

    def execute(self):
        print(f"Non-additive activity: {self.name}, duration: {self.duration} minutes")

# Manufacture Node: Represents operations that process raw materials
class ManufactureNode(OperationNode):
    def __init__(self, name, material, duration):
        super().__init__(name, duration)
        self.material = material  # material to be processed

    def execute(self):
        print(f"Manufacturing operation: {self.name} on material: {self.material}, duration: {self.duration} minutes")

class PrecedenceGraph(ABC):
    """Base class for precedence graphs, managing nodes and their relationships."""
    def __init__(self):
        self.nodes = []  # List of nodes in the graph

    def add_node(self, node):
        """Add a node to the graph, ensuring it matches the type restrictions of the graph."""
        if self.is_valid_node_type(node):
            self.nodes.append(node)
        else:
            raise TypeError(f"{type(node).__name__} is not allowed in this graph type.")

    @abstractmethod
    def is_valid_node_type(self, node):
        """Check if a node type is allowed in the specific graph type."""
        pass

    def add_dependency(self, predecessor, successor):
        """Add a directed edge from predecessor to successor in the graph."""
        if predecessor in self.nodes and successor in self.nodes:
            successor.add_predecessor(predecessor)
        else:
            raise ValueError("Both nodes must be part of the graph to create a dependency.")

    def execute_graph(self):
        """Execute all nodes in the graph following their dependencies (simple order for demo purposes)."""
        executed_nodes = set()
        for node in self.nodes:
            if all(pred in executed_nodes for pred in node.predecessors):
                node.execute()
                executed_nodes.add(node)

# AssemblyGraph: Only allows AssemblyNodes and NonProductiveActivityNodes
class AssemblyGraph(PrecedenceGraph):
    def is_valid_node_type(self, node):
        return isinstance(node, (AssemblyNode, NonAdditiveActivityNode))

# ManufacturingGraph: Only allows ManufactureNodes and NonProductiveActivityNodes
class ManufacturingGraph(PrecedenceGraph):
    def __init__(self, output_id):
        super().__init__()
        self.output_id = output_id  # Unique identifier for the manufactured component
        self.completed = False  # Status to indicate if the graph has completed execution

    def mark_as_completed(self):
        """Mark this manufacturing process as completed."""
        self.completed = True

    def is_completed(self):
        """Check if this manufacturing process is completed."""
        return self.completed

    def is_valid_node_type(self, node):
        return isinstance(node, (ManufactureNode, NonAdditiveActivityNode))

    def __repr__(self):
        return f"ManufacturingGraph(output_id={self.output_id})"

###########################################################################################
# Example usage by ChatGPT:

'''
# Create nodes
weld = AssemblyNode("Welding", components=["PartA", "PartB"], duration=30)
inspection = NonAdditiveActivityNode("Quality Inspection", duration=10)
cut = ManufactureNode("Cutting", material="Steel Plate", duration=20)

# Create an assembly graph and add nodes
assembly_graph = AssemblyGraph()
assembly_graph.add_node(weld)
assembly_graph.add_node(inspection)
assembly_graph.add_dependency(weld, inspection)

# Execute the assembly graph
assembly_graph.execute_graph()

# Create a manufacturing graph and add nodes
manufacturing_graph = ManufacturingGraph()
manufacturing_graph.add_node(cut)
manufacturing_graph.add_node(inspection)
manufacturing_graph.add_dependency(cut, inspection)

# Execute the manufacturing graph
manufacturing_graph.execute_graph()

# Example for dependencies between ManufacturingGraphs and AssemblyNodes:

# Create manufacturing graphs for components
mfg_graph_A = ManufacturingGraph(output_id="PartA")
mfg_graph_B = ManufacturingGraph(output_id="PartB")

# Mark these graphs as completed for testing
mfg_graph_A.mark_as_completed()
mfg_graph_B.mark_as_completed()

# Create an assembly node that requires these components
assembly = AssemblyNode("AssemblyOperation1", components=["PartA", "PartB"], duration=15)

# Link required manufacturing graphs to the assembly node
assembly.add_required_manufacturing_graph(mfg_graph_A)
assembly.add_required_manufacturing_graph(mfg_graph_B)

# Attempt to execute the assembly node
assembly.execute()
'''