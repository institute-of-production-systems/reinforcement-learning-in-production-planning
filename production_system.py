from copy import copy, deepcopy
from order_list import OrderList, Order
from product_instructions import ProductPalette
from time_series_manager import TimeSeriesManager
import math
from enum import Enum, IntEnum
from file_utils import object_to_dict
from collections import deque
from datetime import datetime
import numpy
import fnmatch

class Machine():
    def __init__(self, machine_id='', accepted_capabilities=list(), provided_capabilities=list(), compatible_tools=list(),
                 software_setup_time_value=0.0, software_setup_time_unit='', software_setup_parallel_to_operation=False,
                 hardware_setup_time_value=0.0, hardware_setup_time_unit='', batch_processing=False, batch_size=dict(),
                 speed_factor=1.0, mtbf_value=math.inf, mtbf_unit='', mttr_value=0.0, mttr_unit='', is_transport=False,
                 diff_comp_batch=False, power_consumption=0.0, hardware_setup_parallel_to_operation=False,
                 setup_matrix=dict(), tool_slots=dict()):
        self.machine_id = machine_id
        self.accepted_capabilities = accepted_capabilities  # What capabilities can be requested by this machine from workers?
        self.provided_capabilities = provided_capabilities  # What capability does this machine provide given all the resources are available?
        self.compatible_tools = compatible_tools  # What tools can be used by this machine?
        self.software_setup_time_value = software_setup_time_value  # 0 if no program or parameter change required for different work objects 
        self.software_setup_time_unit = software_setup_time_unit
        self.software_setup_parallel_to_operation = software_setup_parallel_to_operation  # Can a program for a new part be input while the machine is busy with an operation?
        #self.hardware_setup_time_value = hardware_setup_time_value  # 0 if no tool change required for different work objects
        self.hardware_setup_time_unit = hardware_setup_time_unit
        self.hardware_setup_parallel_to_operation = hardware_setup_parallel_to_operation
        self.batch_processing = batch_processing  # Does this machine work in batches? E.g. ovens, washing machines
        self.batch_size = batch_size  # {component_id: (min.bs, max.bs, qty_step)} - only amounts min.bs+n*qty_step <= max.bs will be allowed for batch processing
        self.speed_factor = speed_factor  # How fast is the machine relative to the standard operation duration? Actual speed in m/s for a transport machine
        self.mtbf_value = mtbf_value
        self.mtbf_unit = mtbf_unit
        self.mttr_value = mttr_value
        self.mttr_unit = mttr_unit
        self.is_transport = is_transport  # Is this a transport machine (not a conveyor, but actual forklift, AGV or robot)
        self.diff_comp_batch = diff_comp_batch  # Can different component (types) be combined in a signle batch?
        self.power_consumption = power_consumption  # Average power consumption of this machine (changing dynamic tool properties is modeled via tool & operation properties!)
        self.setup_matrix = setup_matrix  # How much time does tool exchange take, dict of dict: setup_matrix[<from_tool>][<to_tool>]
        self.tool_slots = tool_slots  # Mapping of tools to slots, dict


    def material_matches_wildcard(self, to_check, regex_string):
        """
        Checks if the given material name matches the wildcard pattern.

        :param to_check: Material name string (e.g., "screw_M6x10").
        :param regex_string: Wildcard pattern string (e.g., "screw*").
        :return: True if it matches, False otherwise.
        """
        return fnmatch.fnmatch(to_check, regex_string)


    def accepts_objects(self, objects : tuple, wip_components : list):
        '''
        Returns True if the objects can be fit into the batch processing machine, False otherwise.

        Args:
            objects (tuple): (component, quantity)
            wip_components (list): list of dictionaries like {'Component': 'abc', 'Quantity': 8}
        '''
        component = objects[0]
        quantity = objects[1]

        if not self.batch_processing:
            return True

        if self.batch_size == {}:
            return True

        allowed_combination_group = ''
        if not self.diff_comp_batch:
            # Find out the allowed combination group of this component if there is any
            for allowed_component_pattern in self.batch_size.keys():
                if self.material_matches_wildcard(component, allowed_component_pattern):
                    allowed_combination_group = self.batch_size[allowed_component_pattern][3]  # "group" index in the tuple
                    break

        for allowed_component_pattern in self.batch_size.keys():
            if not self.diff_comp_batch:
                if not self.material_matches_wildcard(component, allowed_component_pattern):
                    if allowed_combination_group != self.batch_size[allowed_component_pattern][3]:
                        # Find all components in the contents that match the currently checked pattern (from buffer specification table)
                        matching_contents = []
                        for dict in wip_components:
                            comp = dict['Component']
                            qty = dict['Quantity']
                            if self.material_matches_wildcard(comp, allowed_component_pattern) and qty > 0:
                                matching_contents.append(comp)
                        if len(matching_contents) > 0:
                            return False
                    else:
                        if allowed_combination_group == '':
                            # Cannot combine with any other component regex
                            matching_contents = []
                            for dict in wip_components:
                                comp = dict['Component']
                                qty = dict['Quantity']
                                if self.material_matches_wildcard(comp, allowed_component_pattern) and qty > 0:
                                    matching_contents.append(comp)
                            if len(matching_contents) > 0:
                                return False
                        occupied_relative_capacity = 0.0
                        for dict in wip_components:
                            comp = dict['Component']
                            qty = dict['Quantity']
                            for acp in self.batch_size.keys():
                                if self.material_matches_wildcard(comp, acp) and allowed_combination_group == self.batch_size[acp][3]:
                                    occupied_relative_capacity += qty / self.batch_size[acp][1]  # max. quantity in the tuple
                        available_relative_capacity = 1 - occupied_relative_capacity
                        checked_component_max_qty = 0
                        for acp in self.batch_size.keys():
                            if self.material_matches_wildcard(component, acp):
                                checked_component_max_qty = self.batch_size[acp][1]
                                break
                        if checked_component_max_qty == 0:
                            return False
                        if (available_relative_capacity > quantity / checked_component_max_qty or 
                            math.isclose(available_relative_capacity, quantity / checked_component_max_qty)):
                            already_contained_qty = 0
                            for dict in wip_components:
                                comp = dict['Component']
                                qty = dict['Quantity']
                                if comp == component:
                                    already_contained_qty = qty
                            if (already_contained_qty + quantity) % self.batch_size[allowed_component_pattern][2] != 0:  # quantity step in the tuple
                                return False
                            else:
                                return True
                        else:
                            return False

            if self.diff_comp_batch:
                occupied_relative_capacity = 0.0
                for dict in wip_components:
                    comp = dict['Component']
                    qty = dict['Quantity']
                    for acp in self.batch_size.keys():
                        if self.material_matches_wildcard(comp, acp):
                            occupied_relative_capacity += qty / self.batch_size[acp][1]  # max. quantity
                available_relative_capacity = 1 - occupied_relative_capacity
                checked_component_max_qty = 0
                checked_component_qty_step = 0
                for acp in self.batch_size.keys():
                    if self.material_matches_wildcard(component, acp):  # acp
                        checked_component_max_qty = self.batch_size[acp][1]  # max. qunatity
                        checked_component_qty_step = self.batch_size[acp][2]
                        break
                if checked_component_max_qty == 0:
                    return False
                # Note: correct float equality check!
                if (available_relative_capacity > quantity / checked_component_max_qty or
                    math.isclose(available_relative_capacity, quantity / checked_component_max_qty)):
                    already_contained_qty = 0
                    for dict in wip_components:
                        comp = dict['Component']
                        qty = dict['Quantity']
                        if comp == component:
                            already_contained_qty = qty
                    if (already_contained_qty + quantity) % checked_component_qty_step != 0:  # quantity step
                        return False
                    else:
                        break  # return True
                else:
                    return False
        return True # -

    def to_dict(self):
        return {
            "machine_id": self.machine_id,
            "accepted_capabilities": object_to_dict(self.accepted_capabilities),
            "provided_capabilities": object_to_dict(self.provided_capabilities),
            "compatible_tools": object_to_dict(self.compatible_tools),
            "software_setup_time_value": self.software_setup_time_value,
            "software_setup_time_unit": self.software_setup_time_unit,
            "software_setup_parallel_to_operation": self.software_setup_parallel_to_operation,
            "setup_matrix": object_to_dict(self.setup_matrix),
            "hardware_setup_time_unit": self.hardware_setup_time_unit,
            "hardware_setup_parallel_to_operation": self.hardware_setup_parallel_to_operation,
            "tool_slots": object_to_dict(self.tool_slots),
            "batch_processing": self.batch_processing,
            "batch_size": object_to_dict(self.batch_size),
            "diff_comp_batch": self.diff_comp_batch,
            "speed_factor": self.speed_factor,
            "mtbf_value": self.mtbf_value,
            "mtbf_unit": self.mtbf_unit,
            "mttr_value": self.mttr_value,
            "mttr_unit": self.mttr_unit,
            "is_transport": self.is_transport,
            "power_consumption": self.power_consumption
        }


class TransportMachineStatus(IntEnum):
    IDLE = 1
    READY = 2
    MOVING_TO_SOURCE = 3
    EXECUTING_TRANSPORT = 4
    LOADING = 5
    UNLOADING = 6
    WAITING_FOR_WORKER = 7
    MAINTENANCE = 8
    ERROR = 9
    REPAIR = 10


class TransportMachine(Machine):
    '''
    Represents a transport machine for simulation purposes.
    Extends Machine class with additional attributes for tracking in simulation.
    Use Machine class to save static properties.
    '''
    def __init__(self, machine_instance: Machine):
        super().__init__(
            machine_id=machine_instance.machine_id,
            accepted_capabilities=machine_instance.accepted_capabilities.copy(),
            provided_capabilities=machine_instance.provided_capabilities.copy(),
            compatible_tools=machine_instance.compatible_tools.copy(),
            software_setup_time_value=machine_instance.software_setup_time_value,
            software_setup_time_unit=machine_instance.software_setup_time_unit,
            software_setup_parallel_to_operation=machine_instance.software_setup_parallel_to_operation,
            hardware_setup_time_unit=machine_instance.hardware_setup_time_unit,
            hardware_setup_parallel_to_operation=machine_instance.hardware_setup_parallel_to_operation,
            batch_processing=machine_instance.batch_processing,
            batch_size=machine_instance.batch_size.copy(),
            speed_factor=machine_instance.speed_factor,
            mtbf_value=machine_instance.mtbf_value,
            mtbf_unit=machine_instance.mtbf_unit,
            mttr_value=machine_instance.mttr_value,
            mttr_unit=machine_instance.mttr_unit,
            is_transport=True,  # Explicitly setting transport flag
            diff_comp_batch=machine_instance.diff_comp_batch,
            power_consumption=machine_instance.power_consumption,
            setup_matrix=machine_instance.setup_matrix.copy(),
            tool_slots=machine_instance.tool_slots.copy()
        )
        # Additional simulation tracker variables similar to a Workstation
        self.status = list()  # List of TransportMachine stati
        self.transport_order_list = list()  # [{'Component': 'abc', 'Quantity': 8, 'Source': 'Inv1', 'Destination': 'WS1', 'Commitment': True, 'En route': False}, ...]
        self.payload = list()  # Physical objects currently held by this machine, [{'Component': 'abc', 'Quantity': 8}, ...]
        self.current_location : str = 'Shopfloor'  # Can be 'Shopfloor' at start or while moving, Workstation ID or Inventory ID when arrived at destination
        self.departed_from : str = None  # If moving, where did the transport machine depart from? str ID
        self.destination : str = None  # If moving, where is the transport machine heading? str ID
        self.remaining_distance : float = 0.0  # If moving, how far is the transport machine from its current destination? float meters
        self.seized_worker : str = None  # Which Worker is currently operating/ moving the transport machine? str ID
        self.remaining_handling_time : int = 0  # If loading or unloading, how much time is left till it's done? int seconds

    def worker_capabilities_present(self, production_system):
        '''
        Returns (True, None) if the seized worker has necessary capabilitites to drive the transport machine.
        Returns (False, self.accepted_capabilities) if there is no worker although one is needed or worker capabilities do not match.
        '''
        capabilities_present = True
        missing_capabilities = None

        if len(self.accepted_capabilities) == 0:
            # Autonomous vehicle
            return capabilities_present, missing_capabilities
        
        if self.seized_worker is None and len(self.accepted_capabilities) > 0:
            # Transport machine needs some capabilities from workers, but no worker is currently seized
            return False, self.accepted_capabilities
        
        if self.seized_worker is not None:
            worker : Worker = production_system.workers[self.seized_worker]
            missing_capabilities = set(self.accepted_capabilities).difference(worker.provided_capabilities)
            if len(missing_capabilities) > 0:
                missing_capabilities = self.accepted_capabilities
                return False, missing_capabilities
            else:
                return True, None


class WorkerStatus(IntEnum):
    IDLE = 1
    WALKING = 2
    SETTING_UP = 3
    BUSY = 4


class Worker():
    def __init__(self, worker_id='', provided_capabilities=list()):
        self.worker_id = worker_id
        self.provided_capabilities = provided_capabilities  # List of strings (names of worker capabilities)
        # Simulation trackers:
        self.location = ''  # workstation / transport machine / worker pool / shopfloor
        self.destination = ''  # workstation / transport machine
        self.distance_to_destination = 0.0  # in meters
        self.status : WorkerStatus = WorkerStatus.IDLE
        self.busy_time = 0.0
        self.setup_time = 0.0
        self.walking_time = 0.0
        self.status_history = []  # List of tuples like (timestamp, status)

    def to_dict(self):
        return {
            "worker_id": self.worker_id,
            "provided_capabilities": object_to_dict(self.provided_capabilities)
        }
    
    def update_timers(self, delta_t):
        if self.status and self.status == WorkerStatus.BUSY:
            self.busy_time += delta_t
        elif self.status and self.status == WorkerStatus.SETTING_UP:
            self.setup_time += delta_t
        elif self.status and self.status == WorkerStatus.WALKING:
            self.walking_time += delta_t

    def log_status_change(self, change_timestamp):
        if self.status:
            self.status_history.append((change_timestamp, self.status.name))
        else:
            self.status_history.append((change_timestamp, WorkerStatus.IDLE.name))


class Tool():
    '''This can be an actual tool or a helper medium wtih dynamic properties. Tools are additional objects for machines or workstations required for operation execution.'''
    def __init__(self, tool_id='', dynamic_properties=dict(), static_properties=dict()):
        self.tool_id = tool_id
        # Properties of the tool or helper medium that can be changed by setups or by operations (dynamic)
        # dict of dicts: {property: {min:..., max:..., unit:..., time_per_unit_increase, energy_per_unit_increase, cost_per_unit_increase, same for unit decrease...}}
        self.dynamic_properties = dynamic_properties  
        # Static properties of the tool that remain constant for this tool but influence operation execution possibilities
        # dict of dicts: {property: {value:..., unit:...}}
        self.static_properties = static_properties

    def to_dict(self):
        return {
            "tool_id": self.tool_id,
            "dynamic_properties": object_to_dict(self.dynamic_properties),
            "static_properties": object_to_dict(self.static_properties)
        }


class BufferSequenceType(IntEnum):
    FIFO = 1
    LIFO = 2
    FREE = 3
    SOLID_RAW_MATERIAL = 4  # refill only when empty, refill only in a single batch, recapture of unused portion allowed


class BufferLocation(IntEnum):
    IN = 1
    OUT = 2


class InventoryGenerationType(IntEnum):
    BUFFER = 1
    SOURCE = 2
    SINK = 3


class SupplyAllocationType(IntEnum):
    ORDER_SPECIFIC = 1
    ORDER_ANONYMOUS = 2


class Buffer():
    def __init__(self, buffer_location=BufferLocation, idx1=0, diff_comp_comb=False, sequence_type=BufferSequenceType, comp_specific_sizes=dict(), identical_buffer=''):
        self.buffer_location = buffer_location  # IN (1) or OUT (2)
        self.idx1 = idx1  # 1-index of this buffer in the IN or OUT set of parent workstation
        self.diff_comp_comb = diff_comp_comb  # Are different component (types) combinable in this buffer?
        self.sequence_type = sequence_type  # In what sequence can components be taken from this buffer?
        self.comp_specific_sizes = comp_specific_sizes  # How many of each component (type) can this buffer contain?
        self.identical_buffer = identical_buffer  # What input buffer is this one identical to: <workstation_id> : IN/OUT : <idx 1>
        self.fill_level_history = []  # List of tuples (timestamp, fill_level)
        # TODO: If InfluxDB is not an overkill for a single Gantt chart, then integrate it. But currently it seems to be an overkill.
        #self.time_series_manager = TimeSeriesManager()  # For InfluxDB logging

        # Simulation trackers
        self.contents = {}  # component_name: quantity

    def to_dict(self):
        return {
            "buffer_location": self.buffer_location,  # ToDo: check whether Enum gets saved properly in JSON
            "idx1": self.idx1,
            "diff_comp_comb": self.diff_comp_comb,
            "sequence_type": self.sequence_type,
            "comp_specific_sizes": object_to_dict(self.comp_specific_sizes),
            "identical_buffer": self.identical_buffer
        }
    
    def material_matches_wildcard(self, to_check, regex_string):
        """
        Checks if the given material name matches the wildcard pattern.

        :param to_check: Material name string (e.g., "screw_M6x10").
        :param regex_string: Wildcard pattern string (e.g., "screw*").
        :return: True if it matches, False otherwise.
        """
        return fnmatch.fnmatch(to_check, regex_string)
    
    def accepts_objects(self, objects : tuple):
        '''
        Returns True if the objects can be fit into the buffer, False otherwise.

        Args:
            objects (tuple): (component, quantity)
        '''
        component = objects[0]
        quantity = objects[1]

        if self.comp_specific_sizes == {}:
            return True
        
        # Make sure there is a key-value pair to add to in the buffer contents dict
        if component not in self.contents.keys():
            self.contents.update({component: 0})

        allowed_combination_group = ''
        if not self.diff_comp_comb:
            # Find out the allowed combination group of this component if there is any
            for allowed_component_pattern in self.comp_specific_sizes.keys():
                if self.material_matches_wildcard(component, allowed_component_pattern):
                    allowed_combination_group = self.comp_specific_sizes[allowed_component_pattern]['Group']
                    break

        for allowed_component_pattern in self.comp_specific_sizes.keys():
            if not self.diff_comp_comb:
                if allowed_combination_group != self.comp_specific_sizes[allowed_component_pattern]['Group']:
                    # Find all components currently in the buffer that belong to other combination groups
                    matching_contents = []
                    for comp, qty in self.contents.items():
                        if self.material_matches_wildcard(comp, allowed_component_pattern) and qty > 0:
                            matching_contents.append(comp)
                    if len(matching_contents) > 0:
                        # There are already components from other combination groups in the buffer
                        return False
                elif allowed_combination_group == self.comp_specific_sizes[allowed_component_pattern]['Group']:
                    if not self.material_matches_wildcard(component, allowed_component_pattern):
                        if allowed_combination_group == '':
                            matching_contents = []
                            for comp, qty in self.contents.items():
                                if self.material_matches_wildcard(comp, allowed_component_pattern) and qty > 0:
                                    matching_contents.append(comp)
                            if len(matching_contents) > 0:
                                return False
                        occupied_relative_capacity = 0.0
                        for comp, qty in self.contents.items():
                            for acp in self.comp_specific_sizes.keys():
                                if self.material_matches_wildcard(comp, acp) and allowed_combination_group == self.comp_specific_sizes[acp]['Group']:
                                    occupied_relative_capacity += qty / self.comp_specific_sizes[acp]['Max. quantity']
                        available_relative_capacity = 1 - occupied_relative_capacity
                        checked_component_max_qty = 0
                        checked_component_qty_step = 0
                        for acp in self.comp_specific_sizes.keys():
                            if self.material_matches_wildcard(component, acp):
                                checked_component_max_qty = self.comp_specific_sizes[acp]['Max. quantity']
                                checked_component_qty_step = self.comp_specific_sizes[acp]['Quantity step']
                                break
                        if checked_component_max_qty == 0:
                            return False
                        if (available_relative_capacity > quantity / checked_component_max_qty or
                            math.isclose(available_relative_capacity, quantity / checked_component_max_qty)):
                            if (self.contents[component] + quantity) % self.comp_specific_sizes[allowed_component_pattern]['Quantity step'] != 0:
                                # TODO: Products of batch operations (e.g. two operations in the same batch need to be finished
                                # for their products to be accepted in an output buffer)
                                return False
                            else:
                                return True
                        else:
                            return False
                    elif self.material_matches_wildcard(component, allowed_component_pattern):
                        occupied_relative_capacity = 0.0
                        for comp, qty in self.contents.items():
                            for acp in self.comp_specific_sizes.keys():
                                if self.material_matches_wildcard(comp, acp) and allowed_combination_group == self.comp_specific_sizes[acp]['Group']:
                                    occupied_relative_capacity += qty / self.comp_specific_sizes[acp]['Max. quantity']
                        available_relative_capacity = 1 - occupied_relative_capacity
                        checked_component_max_qty = 0
                        checked_component_qty_step = 0
                        for acp in self.comp_specific_sizes.keys():
                            if self.material_matches_wildcard(component, acp):
                                checked_component_max_qty = self.comp_specific_sizes[acp]['Max. quantity']
                                break
                        if checked_component_max_qty == 0:
                            return False
                        if (available_relative_capacity > quantity / checked_component_max_qty or
                            math.isclose(available_relative_capacity, quantity / checked_component_max_qty)):
                            if (self.contents[component] + quantity) % self.comp_specific_sizes[allowed_component_pattern]['Quantity step'] != 0:
                                # TODO: Products of batch operations (e.g. two operations in the same batch need to be finished
                                # for their products to be accepted in an output buffer)
                                return False
                            else:
                                return True
                        else:
                            return False

            if self.diff_comp_comb:
                occupied_relative_capacity = 0.0
                for comp, qty in self.contents.items():
                    for acp in self.comp_specific_sizes.keys():
                        if self.material_matches_wildcard(comp, acp):
                            occupied_relative_capacity += qty / self.comp_specific_sizes[acp]['Max. quantity']
                available_relative_capacity = 1 - occupied_relative_capacity
                checked_component_max_qty = 0
                checked_component_qty_step = 0
                for acp in self.comp_specific_sizes.keys():
                    if self.material_matches_wildcard(component, acp):
                        checked_component_max_qty = self.comp_specific_sizes[acp]['Max. quantity']
                        checked_component_qty_step = self.comp_specific_sizes[acp]['Quantity step']
                        break
                # The component name is not in size specifications
                if checked_component_max_qty == 0:
                    return False
                if (available_relative_capacity > quantity / checked_component_max_qty or
                    math.isclose(available_relative_capacity, quantity / checked_component_max_qty)):
                    #if self.contents[component] + quantity % self.comp_specific_sizes[allowed_component_pattern]['Quantity step'] != 0:
                    if (self.contents[component] + quantity) % checked_component_qty_step != 0:
                        return False
                    else:
                        break  # return True
                else:
                    return False
        return True                    

    def get_fill_level(self):
        '''
        Returns current occupied relative capacity of the Buffer.
        '''
        occupied_relative_capacity = 0.0
        for comp, qty in self.contents.items():
            for acp in self.comp_specific_sizes.keys():
                if self.material_matches_wildcard(comp, acp):
                    occupied_relative_capacity += qty / self.comp_specific_sizes[acp]['Max. quantity']
        return occupied_relative_capacity
    
    def log_fill_level_change(self, change_timestamp):
        '''
        Adds buffer fill level to fill_level_history with the simulation timestamp.
        The responsibility of doing this at the right time in simulation lies on the main simulation loop
        (run_until_decision_point).
        '''
        current_fill_level = self.get_fill_level()
        # Low-level table update
        self.fill_level_history.append((change_timestamp, current_fill_level))
        # TODO: Integrate if necessary
        # InfluxDB
        # self.time_series_manager.log_buffer_state(
        #     workstation_id + " : " + self.buffer_location.name + " : " + str(self.idx1),
        #     current_fill_level,
        #     change_timestamp
        # )

    def get_average_fill_level(self):
        if not self.fill_level_history:
            return 0.0
            
        weighted_sum = 0.0
        total_duration = 0.0
        
        for i in range(len(self.fill_level_history) - 1):
            duration = self.fill_level_history[i+1][0] - self.fill_level_history[i][0]
            fill_level = self.fill_level_history[i][1]
            weighted_sum += duration * fill_level
            total_duration += duration
            
        return weighted_sum / total_duration if total_duration > 0 else 0.0

    def get_fill_level_variability(self):
        if len(self.fill_level_history) < 2:
            return 0.0
            
        avg = self.get_average_fill_level()
        weighted_variance = 0.0
        total_duration = 0.0
        
        for i in range(len(self.fill_level_history) - 1):
            duration = self.fill_level_history[i+1][0] - self.fill_level_history[i][0]
            fill_level = self.fill_level_history[i][1]
            weighted_variance += duration * (fill_level - avg) ** 2
            total_duration += duration
            
        return math.sqrt(weighted_variance / total_duration) if total_duration > 0 else 0.0


class Inventory():
    def __init__(self, inventory_id='', diff_comp_comb=False, generation_type=InventoryGenerationType,
                 sequence_type=BufferSequenceType, comp_specific_sizes=dict(), identical_buffer=''):
        self.inventory_id = inventory_id
        self.diff_comp_comb = diff_comp_comb  # Are different component (types) combinable in this buffer?
        self.generation_type = generation_type  # Are objects in this inventory being stored, produced or consumed?
        self.sequence_type = sequence_type  # In what sequence can components be taken from this buffer?
        self.comp_specific_sizes = comp_specific_sizes  # How many of each component (type) can this buffer contain?
        self.identical_buffer = identical_buffer  # What input buffer is this one identical to: <workstation_id> : IN/OUT : <idx 1>

        # Simulation tracking
        self.contents = {}  # component: quantity

    def remove_objects(self, objects : list):
        '''
        Removes specified objects from the inventory.
        Returns True if successful, False otherwise.
        '''
        success = True
        for move_dict in objects:
            component = move_dict['Component']
            quantity_to_remove = move_dict['Quantity']
            if component in self.contents.keys():
                if self.contents[component] >= quantity_to_remove:
                    self.contents[component] -= quantity_to_remove
                else:
                    success = False
            else:
                success = False
        
        return success
    
    def material_matches_wildcard(self, to_check, regex_string):
        """
        Checks if the given material name matches the wildcard pattern.

        :param to_check: Material name string (e.g., "screw_M6x10").
        :param regex_string: Wildcard pattern string (e.g., "screw*").
        :return: True if it matches, False otherwise.
        """
        return fnmatch.fnmatch(to_check, regex_string)

    def accepts_objects(self, objects : tuple):
        '''
        Returns True if the objects can be fit into the inventory, False otherwise.

        Args:
            objects (tuple): (component, quantity)
        '''
        component = objects[0]
        quantity = objects[1]

        if self.comp_specific_sizes == {}:
            return True
        
        # Make sure there is a key-value pair to add to in the buffer contents dict
        if component not in self.contents.keys():
            self.contents.update({component: 0})

        allowed_combination_group = ''
        if not self.diff_comp_comb:
            # Find out the allowed combination group of this component if there is any
            for allowed_component_pattern in self.comp_specific_sizes.keys():
                if self.material_matches_wildcard(component, allowed_component_pattern):
                    allowed_combination_group = self.comp_specific_sizes[allowed_component_pattern]['Group']
                    break

        for allowed_component_pattern in self.comp_specific_sizes.keys():
            if not self.diff_comp_comb:
                if allowed_combination_group != self.comp_specific_sizes[allowed_component_pattern]['Group']:
                    # Find all components currently in the buffer that belong to other combination groups
                    matching_contents = []
                    for comp, qty in self.contents.items():
                        if self.material_matches_wildcard(comp, allowed_component_pattern) and qty > 0:
                            matching_contents.append(comp)
                    if len(matching_contents) > 0:
                        # There are already components from other combination groups in the buffer
                        return False
                elif allowed_combination_group == self.comp_specific_sizes[allowed_component_pattern]['Group']:
                    if not self.material_matches_wildcard(component, allowed_component_pattern):
                        if allowed_combination_group == '':
                            matching_contents = []
                            for comp, qty in self.contents.items():
                                if self.material_matches_wildcard(comp, allowed_component_pattern) and qty > 0:
                                    matching_contents.append(comp)
                            if len(matching_contents) > 0:
                                return False
                        occupied_relative_capacity = 0.0
                        for comp, qty in self.contents.items():
                            for acp in self.comp_specific_sizes.keys():
                                if self.material_matches_wildcard(comp, acp) and allowed_combination_group == self.comp_specific_sizes[acp]['Group']:
                                    occupied_relative_capacity += qty / self.comp_specific_sizes[acp]['Max. quantity']
                        available_relative_capacity = 1 - occupied_relative_capacity
                        checked_component_max_qty = 0
                        checked_component_qty_step = 0
                        for acp in self.comp_specific_sizes.keys():
                            if self.material_matches_wildcard(component, acp):
                                checked_component_max_qty = self.comp_specific_sizes[acp]['Max. quantity']
                                checked_component_qty_step = self.comp_specific_sizes[acp]['Quantity step']
                                break
                        if checked_component_max_qty == 0:
                            return False
                        if (available_relative_capacity > quantity / checked_component_max_qty or
                            math.isclose(available_relative_capacity, quantity / checked_component_max_qty)):
                            if (self.contents[component] + quantity) % self.comp_specific_sizes[allowed_component_pattern]['Quantity step'] != 0:
                                # TODO: Products of batch operations (e.g. two operations in the same batch need to be finished
                                # for their products to be accepted in an output buffer)
                                return False
                            else:
                                return True
                        else:
                            return False
                    elif self.material_matches_wildcard(component, allowed_component_pattern):
                        occupied_relative_capacity = 0.0
                        for comp, qty in self.contents.items():
                            for acp in self.comp_specific_sizes.keys():
                                if self.material_matches_wildcard(comp, acp) and allowed_combination_group == self.comp_specific_sizes[acp]['Group']:
                                    occupied_relative_capacity += qty / self.comp_specific_sizes[acp]['Max. quantity']
                        available_relative_capacity = 1 - occupied_relative_capacity
                        checked_component_max_qty = 0
                        checked_component_qty_step = 0
                        for acp in self.comp_specific_sizes.keys():
                            if self.material_matches_wildcard(component, acp):
                                checked_component_max_qty = self.comp_specific_sizes[acp]['Max. quantity']
                                break
                        if checked_component_max_qty == 0:
                            return False
                        if (available_relative_capacity > quantity / checked_component_max_qty or
                            math.isclose(available_relative_capacity, quantity / checked_component_max_qty)):
                            if (self.contents[component] + quantity) % self.comp_specific_sizes[allowed_component_pattern]['Quantity step'] != 0:
                                # TODO: Products of batch operations (e.g. two operations in the same batch need to be finished
                                # for their products to be accepted in an output buffer)
                                return False
                            else:
                                return True
                        else:
                            return False

            ### Old version ###

            # if not self.diff_comp_comb:
            #     if not self.material_matches_wildcard(component, allowed_component_pattern):
            #         if allowed_combination_group != self.comp_specific_sizes[allowed_component_pattern]['Group']:
            #             # Find all components in the contents that match the currently checked pattern (from buffer specification table)
            #             matching_contents = []
            #             for comp, qty in self.contents.items():
            #                 if self.material_matches_wildcard(comp, allowed_component_pattern) and qty > 0:
            #                     matching_contents.append(comp)
            #             if len(matching_contents) > 0:
            #                 return False
            #         else:
            #             if allowed_combination_group == '':
            #                 # Cannot combine with any other component regex
            #                 matching_contents = []
            #                 for comp, qty in self.contents.items():
            #                     if self.material_matches_wildcard(comp, allowed_component_pattern) and qty > 0:
            #                         matching_contents.append(comp)
            #                 if len(matching_contents) > 0:
            #                     return False
            #             occupied_relative_capacity = 0.0
            #             for comp, qty in self.contents.items():
            #                 for acp in self.comp_specific_sizes.keys():
            #                     if self.material_matches_wildcard(comp, acp) and allowed_combination_group == self.comp_specific_sizes[acp]['Group']:
            #                         occupied_relative_capacity += qty / self.comp_specific_sizes[acp]['Max. quantity']
            #             available_relative_capacity = 1 - occupied_relative_capacity
            #             checked_component_max_qty = 0
            #             for acp in self.comp_specific_sizes.keys():
            #                 if self.material_matches_wildcard(component, acp):
            #                     checked_component_max_qty = self.comp_specific_sizes[acp]['Max. quantity']
            #                     break
            #             if available_relative_capacity > quantity / checked_component_max_qty:
            #                 if (self.contents[component] + quantity) % self.comp_specific_sizes[allowed_component_pattern]['Quantity step'] != 0:
            #                     return False
            #                 else:
            #                     return True
            #             else:
            #                 return False

            # if self.diff_comp_comb:
            #     occupied_relative_capacity = 0.0
            #     for comp, qty in self.contents.items():
            #         for acp in self.comp_specific_sizes.keys():
            #             if self.material_matches_wildcard(comp, acp):
            #                 occupied_relative_capacity += qty / self.comp_specific_sizes[acp]['Max. quantity']
            #     available_relative_capacity = 1 - occupied_relative_capacity
            #     checked_component_max_qty = 0
            #     for acp in self.comp_specific_sizes.keys():
            #         if self.material_matches_wildcard(component, acp):
            #             checked_component_max_qty = self.comp_specific_sizes[acp]['Max. quantity']
            #             break
            #     if available_relative_capacity > quantity / checked_component_max_qty:
            #         if (self.contents[component] + quantity) % self.comp_specific_sizes[allowed_component_pattern]['Quantity step'] != 0:
            #             return False
            #         else:
            #             return True
            #     else:
            #         return False    

            if self.diff_comp_comb:
                occupied_relative_capacity = 0.0
                for comp, qty in self.contents.items():
                    for acp in self.comp_specific_sizes.keys():
                        if self.material_matches_wildcard(comp, acp):
                            occupied_relative_capacity += qty / self.comp_specific_sizes[acp]['Max. quantity']
                available_relative_capacity = 1 - occupied_relative_capacity
                checked_component_max_qty = 0
                checked_component_qty_step = 0
                for acp in self.comp_specific_sizes.keys():
                    if self.material_matches_wildcard(component, acp):
                        checked_component_max_qty = self.comp_specific_sizes[acp]['Max. quantity']
                        checked_component_qty_step = self.comp_specific_sizes[acp]['Quantity step']
                        break
                # The component name is not in size specifications
                if checked_component_max_qty == 0:
                    return False
                if (available_relative_capacity > quantity / checked_component_max_qty or
                    math.isclose(available_relative_capacity, quantity / checked_component_max_qty)):
                    #if self.contents[component] + quantity % self.comp_specific_sizes[allowed_component_pattern]['Quantity step'] != 0:
                    if (self.contents[component] + quantity) % checked_component_qty_step != 0:
                        return False
                    else:
                        break  # return True
                else:
                    return False

        return True                
    
    def take_objects(self, objects : list):
        '''
        Takes specified objects into the inventory.
        Returns True if successful, False otherwise.
        '''
        success = True
        for move_dict in objects:
            component = move_dict['Component']
            quantity_to_take = move_dict['Quantity']
            move_tuple = (component, quantity_to_take)
            if self.accepts_objects(move_tuple):
                if move_tuple[0] in self.contents.keys():
                    self.contents[move_tuple[0]] += move_tuple[1]
                else:
                    self.contents.update({move_tuple[0]: move_tuple[1]})
            else:
                success = False
        return success

    def to_dict(self):
        return {
            "inventory_id": self.inventory_id,
            "diff_comp_comb": self.diff_comp_comb,
            "generation_type": self.generation_type,
            "sequence_type": self.sequence_type,
            "comp_specific_sizes": object_to_dict(self.comp_specific_sizes),
            "identical_buffer": self.identical_buffer
        }


class SupplyBehaviour():
    def __init__(self, component_id='', allocation_type=SupplyAllocationType, time_unit='', immediate_probability=1.0, min=0, alpha=0, beta=0.0):
        self.component_id = component_id  # For which component or raw metrial this behaviour/ lead time distribution is specified
        self.allocation_type = allocation_type  # Order-specific or order-anonymous?
        self.time_unit = time_unit
        self.immediate_probability = immediate_probability  # How likely is it that this component is readily available in raw material inventory?
        # Parameters of the Gamma distribution describing the lead time in case the component needs to be ordered
        # Note that if immediate_probability == 1.0, Gamma distribution is not created (as no probability remains for it)
        self.min = min  # The delivery will not be earlier than this
        self.alpha = alpha  # aka shape factor: Small value - left-skewed, large value - more like normal distribution
        self.beta = beta  # aka scale factor: how spread out the Gamma distribution is

    def to_dict(self):
        return {
            "component_id": self.component_id,
            "allocation_type": self.allocation_type,
            "time_unit": self.time_unit,
            "immediate_probability": self.immediate_probability,
            "min": self.min,
            "alpha": self.alpha,
            "beta": self.beta
        }


class Conveyor():
    '''
    Connects (in general case multiple!) upstream and downstream workstations via a FIFO material flow.
    '''
    def __init__(self, conveyor_id='', length=0.0, speed=0.0, input_buffers=dict(), output_buffers=dict(), synchronous=False, max_total_capacity=dict(), diff_comp_comb=False,
                 upstream_setup_only_when_empty=False):
        self.conveyor_id = conveyor_id
        self.length = length  # length in meters
        self.speed = speed  # in m/s
        self.input_buffers = input_buffers  # dict: {<workstation>_<idx1>: (Buffer, distance from conveyor start in m)}
        self.output_buffers = output_buffers  # dict: {<workstation>_<idx1>: (Buffer, distance from conveyor start in m)}
        # Whether all objects on this conveyor move synchronously (which will lead to conveyor stop if some objects reach the end of the conveyor and can't be taken from there)
        self.synchronous = synchronous
        self.max_total_capacity = max_total_capacity  # dictionary of object (group) specific maximum total capacity of this conveyor
        self.diff_comp_comb = diff_comp_comb  # whether different object groups can be on this conveyor at the same time
        self.upstream_setup_only_when_empty = upstream_setup_only_when_empty  # e.g., in case of washing conveyors, do we have to wait till the conveyor is empty to change washing medium?

    def to_dict(self):
        return {
            "conveyor_id": self.conveyor_id,
            "length": self.length,
            "speed": self.speed,
            "input_buffers": object_to_dict(self.input_buffers),
            "output_buffers": object_to_dict(self.output_buffers),
            "synchronous": self.synchronous,
            "max_total_capacity": object_to_dict(self.max_total_capacity),
            "diff_comp_comb": self.diff_comp_comb,
            "upstream_setup_only_when_empty": self.upstream_setup_only_when_empty
        }


class WorkstationStatus(IntEnum):
    EMPTY = 1
    IDLE = 2
    WAITING_FOR_MATERIAL = 3
    WAITING_FOR_WORKER = 4
    WAITING_FOR_TOOLS = 5
    SETUP = 6
    BUSY = 7
    BLOCKED = 8
    MAINTENANCE = 9
    ERROR = 10
    REPAIR = 11


class Workstation():
    def __init__(self, workstation_id='', machine='', permanent_tools=list(), seized_tools=list(), allowed_tool_pools=list(),
                 input_operation_buffer=list(), output_operation_buffer=list(), wip_operations=list(),
                 physical_input_buffers=dict(), physical_output_buffers=dict(), wip_components=list(),
                 allowed_worker_pools=list(), seized_worker='', permanent_worker_assignment=False, tools_in_use=list()):
        self.workstation_id = workstation_id
        self.machine = machine  # What machine is located at this workstation ('' if manual workstation)
        self.permanent_tools = permanent_tools  # Tools that are not shared with other workstations
        self.seized_tools = seized_tools  # Tools that are currently at this workstation (but not used) and can be shared with other workstations
        self.tools_in_use = tools_in_use  # Tools that are currently in use by an Operation at this Workstation
        self.allowed_tool_pools = allowed_tool_pools  # Where this workstation can seize tools from
        self.input_operation_buffer = input_operation_buffer  # Operations waiting to be processed by this workstation
        self.output_operation_buffer = output_operation_buffer  # Operations after they are processed by this workstation but before they move to the next step in the workflow
        self.wip_operations = wip_operations  # Operations currently being processed at this workstation (work in progress, WIP), list of tuples (operation_id, product_id, order_id, instance)
        self.physical_input_buffers = physical_input_buffers  # dict: {idx1 : buffer}
        self.physical_output_buffers = physical_output_buffers  # dict: {idx1 : buffer}
        self.wip_components = wip_components # Physical objects currently being processed at this workstation (work in progress, WIP), [{'Component': 'abc', 'Quantity': 8}, ...]
        self.allowed_worker_pools = allowed_worker_pools  # Where this workstation can seize workers from
        self.seized_worker = seized_worker  # Worker currently at this Workstation
        self.permanent_worker_assignment = permanent_worker_assignment # Whether this worker stays at this workstaion
        
        # Simulation tracker variables
        self.status = list()  # Tracks the stati of the Workstation
        self.remaining_setup_time = 0
        self.remaining_maintenance_time = 0
        self.remaining_repair_time = 0
        self.busy_time = 0.0  # cumulative time in status BUSY
        self.setup_time = 0.0  # cumulative time in status SETUP
        self.status_history = []  # List of tuples like (timestamp, new status list)
        self.utilization_history = []  # List of tuples like (timestamp, utilization float 0-1)

        # Simulation helper variables - populated when make_simulatable() of the production system is called
        # Helper lists of workstations' possible provided capabilities, tools and materials
        self.potential_capabilities = list()
        self.potential_tools = list()
        self.potential_materials = dict()  # basically aggregates info of physical input buffers

    def update_timers(self, delta_t):
        if self.status and self.status[-1] == WorkstationStatus.BUSY:
            self.busy_time += delta_t
        elif self.status and self.status[-1] == WorkstationStatus.SETUP:
            self.setup_time += delta_t

    def log_status_change(self, change_timestamp, op_quadruple=None):
        if self.status:
            if self.status[-1] == WorkstationStatus.BUSY and op_quadruple is not None:
                display_op_name = op_quadruple[0]+' | '+op_quadruple[1]+' | '+op_quadruple[2]+' | '+str(op_quadruple[3])
                self.status_history.append((change_timestamp, [display_op_name]))
            else:
                self.status_history.append((change_timestamp, [s.name for s in self.status]))
        else:
            self.status_history.append((change_timestamp, [WorkstationStatus.IDLE.name]))

    def log_utilization_change(self, change_timestamp, elapsed):
        if elapsed <= 0:
            elapsed = 1
        # Compute ratios
        prod_ratio = self.busy_time / elapsed if hasattr(self, "busy_time") else 0.0
        setup_ratio = self.setup_time / elapsed if hasattr(self, "setup_time") else 0.0
        # Add values to time series
        self.utilization_history.append((change_timestamp, prod_ratio))

    def move_objects_to_physical_output_buffer(self, objects_to_move : list, production_system):
        '''
        Moves specified quantities of objects from the workstation's wip_components to the first
        compatible physical output buffer with enough capacity.

        Returns a tuple with three values:
        1. True if the objects have been successfully moved, False otherwise.
        2. 1-index of the output buffer where the objects have been moved to.
        3. List of Component-Quantity dictionaries of all moved objects.
        '''
        success = False
        output_idx1 = None
        moved_objects = None

        # Aggregate wip_components by component name
        agg_wip_components = []
        # Make a set of unique component names in wip_components
        unique_comp = list(set([cq_dict['Component'] for cq_dict in self.wip_components]))
        # Count components and write the result in the aggregated version
        for comp_id in unique_comp:
            agg_item = {'Component': comp_id, 'Quantity': 0}
            for wip_item in self.wip_components:
                if wip_item['Component'] == comp_id:
                    agg_item['Quantity'] += wip_item['Quantity']
            agg_wip_components.append(agg_item)
        # Replace wip_components of the workstation with the aggregated version
        self.wip_components = agg_wip_components

        for move_dict in objects_to_move:
            component = move_dict['Component']
            quantity = move_dict['Quantity']
            for wip_dict in self.wip_components:
                if wip_dict['Component'] == component:
                    # TODO check this for batched operations
                    #assert wip_dict['Quantity'] - quantity >= 0
                    # Find compatible physical output buffer with enough space
                    buffer : Buffer = self.find_physical_output_buffer((component, quantity), production_system)
                    if buffer is not None:
                        wip_dict['Quantity'] -= min(quantity, wip_dict['Quantity'])
                        # if wip_dict['Quantity'] == 0:
                        #     self.wip_components.remove(wip_dict)
                        if component in buffer.contents.keys():
                            #assert buffer.contents[component] >= 0
                            buffer.contents[component] += quantity
                        else:
                            buffer.contents.update({component: quantity})
                        buffer.log_fill_level_change(production_system.timestamp)
                        return True, buffer.idx1, objects_to_move
                    elif buffer is None:
                        return False, None, [{'Component': component, 'Quantity': 0}]
                    
        return success, output_idx1, moved_objects
    
    def take_objects_into_physical_input_buffers(self, objects : list, timestamp=0):
        '''
        Places the objects into compatible physical input buffers of the workstation with enough capacity.
        Returns True if successful, False otherwise.
        '''
        success_count = 0
        for move_dict in objects:
            move_tuple = (move_dict['Component'], move_dict['Quantity'])
            for buffer in self.physical_input_buffers.values():
                if buffer.accepts_objects(move_tuple):
                    if move_tuple[0] in buffer.contents.keys():
                        buffer.contents[move_tuple[0]] += move_tuple[1]
                    else:
                        buffer.contents.update({move_tuple[0]: move_tuple[1]})
                    if timestamp > 0:
                        buffer.log_fill_level_change(timestamp)
                    success_count += 1
                    break
        if success_count == len(objects):
            return True
        else:
            print('Not all objects could be accepted by workstation buffers:')
            print(f'    objects: {str(objects)}')
            print(f'    workstation: {self.workstation_id}')
            return False


    def find_physical_output_buffer(self, objects_to_move : tuple, production_system):
        '''
        Returns a Buffer that is technically fit to contain the specified quantity of a component.
        Also generates a MaterialsArrivalEvent at that Buffer's identical input buffer of another
        workstation if there is such.

        Args:
            objects_to_move (tuple): (component_name, quantity)
        '''
        for buffer in self.physical_output_buffers.values():
            # Check for identical buffers (i.e. input buffers of other workstations)
            is_identical_buffer = False
            if buffer.identical_buffer != '':
                is_identical_buffer = True
                identical_buffer_str_split = buffer.identical_buffer.split(' : ')
                other_workstation_id = identical_buffer_str_split[0]
                buffer_idx1 = int(identical_buffer_str_split[2])
                other_workstation = production_system.workstations[other_workstation_id]
                buffer = other_workstation.physical_input_buffers[buffer_idx1]
            if buffer.accepts_objects(objects_to_move):
                if is_identical_buffer:
                    # Generate MaterialsArrivalEvent for the workstation connected via identical buffer
                    production_system.event_queue.append(MaterialsArrivalEvent(timestamp=production_system.timestamp,
                                                                workstation=other_workstation,
                                                                component_dict={objects_to_move[0]: objects_to_move[1]}))
                else:
                    # Operation products will then be moved into the workstation's physical output buffer and need to be transported
                    # to further workstations. A PickupRequest is generated in the event handling loop of run_until_decision_point().
                    pass
                return buffer
        return None
    

    def remove_objects_from_output_buffers(self, objects : list, timestamp=0):
        '''
        Removes specified objects from physical output buffers of the workstation.
        Returns True if successful, False otherwise.
        '''
        success = True
        for move_dict in objects:
            component = move_dict['Component']
            quantity_to_remove = move_dict['Quantity']
            already_removed_qty = 0
            for buffer in self.physical_output_buffers.values():
                if component in buffer.contents.keys():
                    if buffer.contents[component] >= quantity_to_remove:
                        buffer.contents[component] -= quantity_to_remove
                        already_removed_qty = quantity_to_remove
                    else:
                        already_removed_qty += buffer.contents[component]
                        buffer.contents[component] = 0
                    if timestamp > 0:
                        buffer.log_fill_level_change(timestamp)
            if already_removed_qty != quantity_to_remove:
                success = False
        
        return success


    def to_dict(self):
        return {
            "workstation_id": self.workstation_id,
            "machine": self.machine,
            "permanent_tools": object_to_dict(self.permanent_tools),
            "seized_tools": object_to_dict(self.seized_tools),
            "tools_in_use": object_to_dict(self.tools_in_use),
            "allowed_tool_pools": object_to_dict(self.allowed_tool_pools),
            "input_operation_buffer": object_to_dict(self.input_operation_buffer),
            "output_operation_buffer": object_to_dict(self.output_operation_buffer),
            "wip_operations": object_to_dict(self.wip_operations),
            "physical_input_buffers": object_to_dict(self.physical_input_buffers),
            "physical_output_buffers": object_to_dict(self.physical_output_buffers),
            "wip_components": object_to_dict(self.wip_components),
            "allowed_worker_pools": object_to_dict(self.allowed_worker_pools),
            "seized_worker": self.seized_worker,
            "permanent_worker_assignment": self.permanent_worker_assignment
        }


class WorkerPool():
    pass


class ToolPool():
    pass


class Event():
    '''Whenever anything workflow-related or performance-related happens in a production system, an Event is created.
    '''
    def __init__(self, timestamp : int):
        self.timestamp = timestamp  # Occurence time of this Event, expressed as seconds since epoch 1970 (UTC), see QDateTime.toSecsSinceEpoch() for more details
        print(f'\n*** New event at timestamp {datetime.fromtimestamp(self.timestamp).strftime(f'%d.%m.%Y %H:%M:%S')}')


class TransportOrder(Event):
    '''Whenever certain quantities of components have to be transported from a source to a destination.
    '''
    def __init__(self, timestamp : int, component_dict : dict, source : Workstation | Inventory | tuple, destination : Workstation | Inventory | tuple):
        super().__init__(timestamp)
        self.component_dict = component_dict  # {component_name (str): quantity (int)}
        self.source = source  # workstation or inventory as objects, buffer as a workstation-buffer tuple 
        self.destination = destination
        print(f'--- New TransportOrder for components {str(self.component_dict)}')


class MaterialsRequest(Event):
    '''Whenever the agent should know that certain quantities of components are required by a workstation for an assigned operation.
    '''        
    def __init__(self, timestamp : int, component_dict : dict, target_workstation : Workstation, order_id=''):
        super().__init__(timestamp)
        self.component_dict = component_dict  # {component_name (str): quantity (int)}
        self.target_workstation = target_workstation
        self.order_id = order_id  # Necessary for order-specific material requests
        print(f'??? New MaterialsRequest for components {str(self.component_dict)}')


class ToolsRequest(Event):
    '''Whenever the agent should know that certain tools are required by a workstation for a committed operation.
    '''
    def __init__(self, timestamp : int, tools : dict, target_workstation : Workstation):
        super().__init__(timestamp)
        self.tools = tools  # {tool_id: {property: {Min, Max, Unit, a, b, c}}}
        self.target_workstation = target_workstation
        # Helper variables to only selectively trigger re-handling of a ToolsRequest
        self.just_created = True
        self.some_unavailable_tool_released = False
        print(f'??? New ToolsRequest for tools {str(self.tools)}')


class WorkerCapabilitiesRequest(Event):
    '''Whenever the agent should know that certain worker capabilities are required by a workstation for a committed operation.
    '''
    def __init__(self, timestamp : int, capability_list : list, target : Workstation | TransportMachine):
        super().__init__(timestamp)
        self.capability_list = capability_list  # [worker_capability (str)]
        self.target = target
        # Helper variables to only selectively trigger re-handling of a WorkerCapabilitiesRequest
        self.just_created = True
        self.some_worker_released = False
        print(f'??? New WorkerCapabilitiesRequest for  {str(self.capability_list)}')


class SetupFinishedEvent(Event):
    '''Whenever a setup is finished at a workstation.
    '''
    def __init__(self, timestamp : int, workstation : Workstation):
        super().__init__(timestamp)
        self.workstation = workstation
        print(f'~~~ New SetupFinishedEvent at {self.workstation.workstation_id}')


class MaintenanceFinishedEvent(Event):
    '''Whenever a maintenance is finished at a workstation.
    '''
    def __init__(self, timestamp : int, workstation : Workstation):
        super().__init__(timestamp)
        self.workstation = workstation
        print(f'    New MaintenanceFinishedEvent at {self.workstation.workstation_id}')


class RepairFinishedEvent(Event):
    '''Whenever a repair is finished at a workstation.
    '''
    def __init__(self, timestamp : int, workstation : Workstation):
        super().__init__(timestamp)
        self.workstation = workstation
        print(f'    New RepairFinishedEvent at {self.workstation.workstation_id}')


class PickupRequest(Event):
    '''Whenever something needs to be transported from an output buffer (e.g. to resolve blocking).
    '''
    def __init__(self, timestamp : int, workstation : Workstation, output_buffer_idx1 : int, objects : list):
        super().__init__(timestamp)
        self.workstation = workstation
        self.output_buffer_idx1 = output_buffer_idx1
        self.objects = objects  # list of Component-Quantity dictionaries
        # Idea:
        #self.order_id = order_id  # If not empty, then only a MaterialsRequest with the same specified order ID can be matched to this PickupRequest
        # However, the decision whether internal products can only be processed order-specific would enforce pure pull logic everywhere.
        # That is not necessarily always needed. We leave RL this flexibility to learn a dynamic mixture of push and pull...
        print(f'??? New PickupRequest from {self.workstation.workstation_id}')
        print(f'    for the objects {str(self.objects)}')



class OperationFinishedEvent(Event):
    '''Whenever an operation is finished at a workstation.
    '''
    def __init__(self, timestamp : int, workstation : Workstation, operation_id : tuple):
        super().__init__(timestamp)
        self.workstation = workstation
        self.operation_id = operation_id  # in the format (operation_id, product_id, order_id, instance)
        self.trigger_push_operation_downstream = False
        print(f'$$$ New OperationFinishedEvent at {self.workstation.workstation_id} for operation {str(self.operation_id)}')


class WorkerStationArrivalEvent(Event):
    '''Whenever a worker arrives at a workstation.
    '''
    def __init__(self, timestamp : int, workstation : Workstation, worker : Worker):
        super().__init__(timestamp)
        self.workstation = workstation
        self.worker = worker
        print(f'>>> New WorkerStationArrivalEvent of worker {self.worker.worker_id if worker else '(no worker)'} at workstation {self.workstation.workstation_id}')


class ToolArrivalEvent(Event):
    '''Whenever a tool arrives at a workstation.
    '''
    def __init__(self, timestamp : int, workstation : Workstation, tool : Tool):
        super().__init__(timestamp)
        self.workstation = workstation
        self.tool = tool
        print(f'>>> New ToolArrivalEvent of tool {self.tool.tool_id} at workstation {self.workstation.workstation_id}')

class ToolReleaseEvent(Event):
    '''Whenever a tool is returned to its tool pool of origin.
    '''
    def __init__(self, timestamp : int, workstation : Workstation, tool : Tool):
        super().__init__(timestamp)
        self.workstation = workstation
        self.tool = tool
        print(f'<<< New ToolReleaseEvent of tool {self.tool.tool_id} from workstation {self.workstation.workstation_id}')

class WorkerReleaseEvent(Event):
    '''Whenever a worker becomes available for other workstations to seize.
    '''
    def __init__(self, timestamp : int, workstation : Workstation, worker : Worker):
        super().__init__(timestamp)
        self.workstation = workstation
        self.worker = worker
        print(f'<<< New WorkerReleaseEvent of worker {self.worker.worker_id} from workstation {self.workstation.workstation_id}')

class MaterialsArrivalEvent(Event):
    '''Whenever a certain quantity of components/materials arrives at a workstation.
    '''
    def __init__(self, timestamp : int, workstation : Workstation, component_dict : dict):
        super().__init__(timestamp)
        self.workstation = workstation
        self.component_dict = component_dict  # {component_name (str): quantity (int)}
        self.buffer_overflow = False
        print('>>> New MaterialsArrivalEvent:')
        print(f'    materials: {str(self.component_dict)}')
        print(f'    workstation: {self.workstation.workstation_id}')


class WorkstationPickupEvent(Event):
    '''Whenever something is transported from an output buffer (e.g. to resolve blocking).
    '''
    def __init__(self, timestamp : int, workstation : Workstation):
        super().__init__(timestamp)
        self.workstation = workstation
        print(f'<<< New WorkstationPickupEvent from {self.workstation.workstation_id}')

class WorkerTransportArrivalEvent(Event):
    '''Whenever a worker arrives at a transport machine.
    '''
    def __init__(self, timestamp : int, transport_machine : TransportMachine, worker : Worker):
        super().__init__(timestamp)
        self.transport_machine = transport_machine
        self.worker = worker
        print(f'>>> New WorkerTransportArrivalEvent of worker {self.worker.worker_id} at transport machine {self.transport_machine.machine_id}')

class TransportArrivalEvent(Event):
    '''Whenever a transport machine arrives at its destination.
    '''
    def __init__(self, timestamp : int, transport_machine : TransportMachine, destination : Workstation | Inventory | Buffer):
        super().__init__(timestamp)
        self.transport_machine = transport_machine
        self.destination = destination
        dest_str = ''
        if isinstance(destination, Inventory):
            dest_str = destination.inventory_id
        if isinstance(destination, Workstation):
            dest_str = destination.workstation_id
        if isinstance(destination, Buffer):
            dest_str = str(destination)
        print(f'>>> New TransportArrivalEvent of transport machine {self.transport_machine.machine_id} at {dest_str}')

class LoadingFinishedEvent(Event):
    '''Whenever components are loaded on a transport machine.
    '''
    def __init__(self, timestamp : int, transport_machine : TransportMachine, location : Workstation | Inventory | tuple, objects : list):
        super().__init__(timestamp)
        self.transport_machine = transport_machine
        self.location = location  # workstation or inventory as objects, buffer as a workstation-buffer tuple 
        self.objects = objects
        print('&&& New LoadingFinishedEvent:')
        print(f'    transport machine: {self.transport_machine.machine_id}')
        print(f'    objects: {str(self.objects)}')

class UnloadingFinishedEvent(Event):
    '''Whenever components are unloaded from a transport machine.
    '''
    def __init__(self, timestamp : int, transport_machine : TransportMachine, location : Workstation | Inventory | Buffer, objects : list):
        super().__init__(timestamp)
        self.transport_machine = transport_machine
        self.location = location
        self.objects = objects
        print('&&& New UnloadingFinishedEvent:')
        print(f'    transport machine: {self.transport_machine.machine_id}')
        print(f'    objects: {str(self.objects)}')


class RawMaterialArrivalEvent(Event):
    '''Whenever raw material (from outside the controlled system) arrives at an inventory or a buffer.
    '''
    def __init__(self, timestamp : int, inventory : Inventory | Buffer, component_dict : dict, order_id=''):
        super().__init__(timestamp)
        self.inventory = inventory
        self.component_dict = component_dict
        self.order_id = order_id  # Necessary for order-specific material supply
        self.rmi_overflow = False  # Flag to handle raw material overflow
        print('>>> New RawMaterialArrivalEvent:')
        print(f'    inventory: {self.inventory.inventory_id}')
        print(f'    objects: {str(self.component_dict)}')


class OrderReleaseEvent(Event):
    '''Whenever an order becomes known and available to the agent for planning.
    '''
    def __init__(self, timestamp : int, order : Order):
        super().__init__(timestamp)
        self.order = order
        print(f'+++ New OrderReleaseEvent for order {self.order.order_id}')


class WorkstationSequencingPostponed(Event):
    '''Whenever a sequencing decision at a workstation is postponed (until the time coinciding with next event in the event queue).
    '''
    def __init__(self, timestamp : int, workstation : Workstation):
        super().__init__(timestamp)
        self.workstation = workstation
        print(f'... New WorkstationSequencingPostponed at {self.workstation.workstation_id}')


class WorkstationRoutingPostponed(Event):
    '''Whenever a routing decision to downstream workstations is postponed (until the time coinciding with next event in the event queue).
    '''
    def __init__(self, timestamp : int, workstation : Workstation):
        super().__init__(timestamp)
        self.workstation = workstation
        print(f'... New WorkstationRoutingPostponed at {self.workstation.workstation_id}')

class TransportSequencingPostponed(Event):
    '''Whenever a sequencing decision at a transport machine is postponed (until the time coinciding with next event in the event queue).
    '''
    def __init__(self, timestamp : int, transport_machine : TransportMachine):
        super().__init__(timestamp)
        self.transport_machine = transport_machine
        print(f'... New TransportSequencingPostponed at {self.transport_machine.machine_id}')


class TransportRoutingPostponed(Event):
    '''Whenever a routing decision to transport machines is postponed (until the time coinciding with next event in the event queue).
    '''
    def __init__(self, timestamp : int, component_dict : dict, source : Workstation | Inventory | Buffer, destination : Workstation | Inventory | Buffer):
        super().__init__(timestamp)
        self.component_dict = component_dict
        self.source = source
        self.destination = destination
        print(f'... New TransportRoutingPostponed')


class OperationStatus(IntEnum):
    IN_BACKLOG = 1
    ASSIGNED = 2
    COMMITTED = 3
    PROCESSING = 4
    FAILED = 5  # If a machine error occurs while processing the operation
    DONE = 6


class ActionType(IntEnum):
    WORKSTATION_ROUTING = 1
    WORKSTATION_SEQUENCING = 2
    TRANSPORT_SEQUENCING = 3
    TRANSPORT_ROUTING = 4


class ProductionSystem():
    '''
    Stores all information of the production system.
    '''
    def __init__(self, order_list=OrderList(), workstations=dict(), worker_pools=dict(), tool_pools=dict(), workers=dict(), machines=dict(), tools=dict(),
                 conveyors=dict(), inventories=dict(), supply_behaviours=dict(), distance_matrix=dict(),
                 worker_capabilities=list(), machine_capabilities=list(), product_instructions=ProductPalette(),
                 event_queue=deque()):
        self.order_list : OrderList = order_list  # What orders did our production system get?
        self.workstations : dict = workstations  # What workstations do we have to fulfill these orders?
        self.worker_pools : dict = worker_pools  # What workers (and worker groups) do we have?
        self.tool_pools : dict = tool_pools  # What tools do our production resources have or share?
        self.workers : dict = workers  # Helper variable to store Worker data even before they are assigned to any pools (for the GUI)
        self.machines : dict = machines  # All machines including transport {machine_id: Machine object}
        self.tools : dict = tools  # All tools (dictionary: {tool_id: Tool object})
        self.conveyors : dict = conveyors  # All conveyors (dictionary: {conveyor_id: Conveyor object})
        self.inventories : dict = inventories  # All inventories (i.e. places where objects are generated, independently stored or destroyed)
        self.supply_behaviours : dict = supply_behaviours  # How input objects are generated / are available
        self.distance_matrix : dict = distance_matrix  # Dict of dicts, reference like this: distance_matrix[<id_from>][<id_to>]
        self.worker_capabilities : list = worker_capabilities  # List of string IDs of worker capabilities (for display purposes in Production Resources tab)
        self.machine_capabilities : list = machine_capabilities  # List of string IDs of machine capabilities (for display purposes)
        self.product_instructions : ProductPalette = product_instructions  # All products that this production system is designed to produce
        self.walking_speed : float = 1.4  # Average walking speed of the workers, float m/s
        self.energy_costs : float = 0.0  # Energy costs in Cent/kWh

        # Simulation helper and tracker variables
        self.stationary_machines = dict()  # Prepared on first simulation start by collecting Machines with is_transport=False
        self.transport_machines = dict()  # Prepared on first simulation start by transforming Machines with is_transport=True into TransportMachines
        self.event_queue : deque = event_queue  # A double-ended queue (deque) that contains Events sorted by time, and preserving the order of simultaneous Events FIFO
        self.start_timestamp : int = 0  # Following QDateTime.toSecsSinceEpoch()
        self.timestamp : int = 0  # Following QDateTime.toSecsSinceEpoch()
        self.end_timestamp : int = 0  # Following QDateTime.toSecsSinceEpoch()
        self.T0 : int = 0  # Simulation start time, constant 0 seconds (int)
        self.t : int = 0  # Current simulation time from start in seconds (int)
        self.te : int = -1  # Simulation end time (seconds) from start of the simulation (int)
        self.order_progress = dict()  # Tracks the progress of orders down to single instances of products and their operations (example below):
        _example_order_progress = {
            'order_id_1': {
                'product_progress': [
                    # instances:
                    {
                        'product_id': 'product_1',
                        'product_instance': 0,
                        'operation_progress': {
                            'operation_a': {
                                'predecessors': [],
                                'location': 'workstation_D',
                                'status': OperationStatus.PROCESSING,
                                'remaining_work': 10
                            },
                            'operation_b': {
                                'predecessors': ['operation_a'],
                                'location': None,
                                'status': OperationStatus.IN_BACKLOG,
                                'remaining_work': 55
                            },
                            'operation_c': {
                                'predecessors': ['operation_b'],
                                'location': 'workstation_E',
                                'status': OperationStatus.ASSIGNED,
                                'remaining_work': 32
                            }
                        },
                        'production_end_time': None,
                        'productive_time': 120,
                        'critical_path_duration': 500
                     },
                    {
                        'product_id': 'product_1',
                        'product_instance': 1,
                        'operation_progress': {
                            'operation_a': {
                                'location': 'workstation_D',
                                'status': OperationStatus.ASSIGNED,
                                'remaining_work': 28
                            },
                            'operation_b': {
                                'location': 'workstation_F',
                                'status': OperationStatus.DONE,
                                'remaining_work': 0
                            },
                            'operation_c': {
                                'location': 'workstation_E',
                                'status': OperationStatus.COMMITTED,
                                'remaining_work': 32
                            }
                        },
                        'production_end_time': None,
                        'productive_time': 360,
                        'critical_path_duration': 500
                     },
                ],
                'release_time' : 123456789,
                'deadline': 134567890
            },
            'order_id_2': {
                'product_progress': [
                    
                ]
            }
                          }
        self.product_operations = dict()  # Used to efficiently represent actions and observations by giving operation (node) lists instead of precedence links (edges)
        self.worker_pool_tracker = dict()  # {worker_pool_id: [worker_id_1, worker_id_2]} - updated dynamically! worker_pools is just static information about worker pool composition!
        self.tool_pool_tracker = dict()  # analog to worker_pool_tracker
        self.tool_state_tracker = dict()  # Almost same structure as operations' tools dict, only with the current values of properties instead
        self.raw_material_names = list()  # To quickly discern between externally ordered / supplied materials and system-internal products
        self.last_materials_request : MaterialsRequest = None  # To avoid material request fulfillment of other identical operations

        # RL observation space configuration
        self.raw_observation_vector_sizes = dict()  # Will give the number of flattened vector entries resulting from observing certain raw state variables
        self.agg_observation_vector_sizes = dict()  # Same for aggregated state variables

        # Action space encoding as a single matrix (similar to a game board):
        # Rows: operations (unique per customer order) + transport machines + 1 row for decision skipping
        # Columns: workstations + inventories + 1 column for decision skipping
        # Values: 0 if action not available, 1 if legal and available action
        # The action is encoded as an integer coordinate in the flattened action space matrix.
        # Note: in terms of selecting an action, there is no difference between instances/copies
        # of the same product within the same customer order since they share the same deadline.
        # This "condensation" trick can reduce the dimension of action and observation spaces multiple times.
        self.action_matrix_n_rows = 0
        self.action_matrix_n_cols = 0
        self.action_matrix_row_dict = {}  # to get integer index by string name
        self.action_matrix_col_dict = {}
        self.action_matrix_reverse_row_dict = {}  # to get string name by integer index
        self.action_matrix_reverse_col_dict = {}
        self.action_matrix = None

        # The simulation logic (set_action within step function) should provide following information about the required actions:
        # 1. Workstation routing: tuple (operation_id, product_id, order_id), list of eligible workstations' IDs
        # 2. Workstation sequencing: workstation_id, list of tuples like (operation_id, product_id, order_id) or ('skip', None, None)
        # 3. Transport sequencing (transport machine chooses among possible destinations): transport machine ID, list of workstation IDs or inventory IDs or 'skip'
        # 4. Transport routing (workstation or inventory chooses among possible transport machines to pickup produced units): (component_dict, source, destination, eligible_transport)
        self.required_action_type : ActionType = None
        self.action_relevant_info = tuple()

        # Optimization/planning run configurations that influence the system behaviour, extracted from AIOptimizationTab
        self.planning_algorithm = ''
        self.algorithm_parameters = {}  # key: parameter name (str), value: parameter value (str!) - only relevant for RL
        self.observation_config = {}  # key: variable/KPI name (str), value: observed? (boolean)
        self.action_config = {}  # key: decision type (str), value: tuple(direct action? (boolean), indirect heuristic name (str))
        self.reward_config = {}  # key: KPI name (str), value: tuple('Ignore'/'Reward'/'Punish' (str), 1-point scale value (float), unit (str))

        self.is_prepared = False  # To track whether make_simulatable() has been calledon this production system object

    def get_int_seconds(self, time_value, time_unit):
        '''Converts any duration represented as combination of time value and unit into integer seconds, ceiling rounding.'''
        # TODO: If no time unit was selected, it is most likely that time input was ignored completely.
        # Maybe some input checks will be needed at the data input stage.
        if time_unit is None or time_unit == '':
            return 0
        if time_unit == 's':
            return math.ceil(time_value)
        elif time_unit == 'min':
            return math.ceil(time_value * 60)
        elif time_unit == 'h':
            return math.ceil(time_value * 60 * 60)
        elif time_unit == 'd':
            return math.ceil(time_value * 24 * 60 * 60)
        else:
            print(f'{time_unit} is not a supported time unit.')
            raise NotImplementedError


    def get_distance(self, from_id : str, to_id: str):
        '''
        Looks up distances in meters in the distance matrix (dictionary).
        '''
        distance = 0.0
        if from_id == '' or from_id is None:
            # Case on init when workers are at their worker pools
            # and transport machines are not explicitly anywhere.
            # Simplification: the first walking time from the worker pool
            # to a workstation / transport machine is not modelled.
            # Same for the first time when transport machine goes to pickup location. 
            return distance
        first_attempt_failed = False
        try:
            distance = self.distance_matrix[from_id][to_id]
        except KeyError:
            first_attempt_failed = True
        if first_attempt_failed:
            try:
                distance = self.distance_matrix[to_id][from_id]
            except KeyError:
                print(f'Warning: unknown distance between {from_id} and {to_id}. Assuming negligible distance.')
                return 0.0
        return distance


    def find_potential_capabilities(self, workstation : Workstation):
        '''Populates the list of all capabilities (machine and worker) that can be provided by a given workstation.'''
        pot_capa = []
        if workstation.machine != '':
            pot_capa += self.machines[workstation.machine].provided_capabilities
            pot_capa += self.machines[workstation.machine].accepted_capabilities
        if len(workstation.allowed_worker_pools) > 0:
            for awp in workstation.allowed_worker_pools:
                for worker in self.worker_pools[awp]:
                    pot_capa += self.workers[worker].provided_capabilities
        if workstation.permanent_worker_assignment:
            assert workstation.seized_worker != ''
            pot_capa += self.workers[workstation.seized_worker].provided_capabilities
        workstation.potential_capabilities = list(set(pot_capa))
    

    def find_potential_tools(self, workstation : Workstation):
        '''Populates the list of all tools that can be provided by a given workstation.'''
        pot_tools = []
        if len(workstation.permanent_tools) > 0:
            pot_tools += workstation.permanent_tools
        if workstation.machine != '':
            # Don't forget to check whether the machine's compatible tools are also available in one of the allowed tool pools of the workstation
            allowed_tools = []
            for atp in workstation.allowed_tool_pools:
                for tool in self.tool_pools[atp]:
                    allowed_tools.append(tool)
            pot_tools += list(set.intersection(set(self.machines[workstation.machine].compatible_tools), set(allowed_tools)))
        else:
            # In case of a manual workstation, the assumption is that all allowed tools can also be seized by the workstation
            for atp in workstation.allowed_tool_pools:
                pot_tools += atp
        workstation.potential_tools = list(set(pot_tools))
    

    def find_potential_materials(self, workstation : Workstation):
        '''Populates the dictionary with component specific maximum input buffer sizes of a given workstation.'''
        # TODO: Maybe here also the quantity step needs to be considered, but it actually concerns transport simulation much more...
        pot_material_capacity = {}
        for phib in workstation.physical_input_buffers.values():
            if phib.comp_specific_sizes == {}:
                # Note: default buffer specification is that of infinite capacity for whatever material.
                # As soon as the buffer size is specified even for a single component,
                # the assumption is that this is the only material technically allowed in the buffer.
                pot_material_capacity.update({"*": math.inf})
                continue
            for material, specs in phib.comp_specific_sizes.items():
                max_qty = specs['Max. quantity']
                if material in pot_material_capacity.keys():
                    if max_qty > pot_material_capacity[material]:
                        pot_material_capacity[material] = max_qty
                else:
                    pot_material_capacity.update({material: max_qty})
        workstation.potential_materials = pot_material_capacity


    def material_matches_wildcard(self, to_check, regex_string):
        """
        Checks if the given material name matches the wildcard pattern.

        :param to_check: Material name string (e.g., "screw_M6x10").
        :param regex_string: Wildcard pattern string (e.g., "screw*").
        :return: True if it matches, False otherwise.
        """
        return fnmatch.fnmatch(to_check, regex_string)


    def get_source_inventory_with_materials(self, materials_tuple, ignore_qty_step=False):
        '''
        Finds a source Inventory that currently contains or can potentially contain requested material in requested quantity. 

        :param materials_tuple (tuple): Requested material in the form (material_name (str): quantity (int)).
        :param ignore_qty_step (bool): False by default, but can be set to True if batch operations can only reach the quantity step when bundled.
        
        :return source_inventory (Inventory): Inventory object, None if the production system doesn't have sources for such materials in such quantities.
        :return material_available (bool): True if the inventory currently contains materials_tuple, False if an order needs to be placed.
        '''
        source_inventory = None
        material_available = False

        material = materials_tuple[0]
        quantity = materials_tuple[1]

        for inventory_id, inventory in self.inventories.items():
            if inventory.generation_type == InventoryGenerationType.SOURCE:
                # Find matching wildcard pattern in the comp.size specification to check quantity step
                matching_pattern = ''
                for wildcard in inventory.comp_specific_sizes.keys():
                    if self.material_matches_wildcard(material, wildcard):
                        matching_pattern = wildcard
                        break
                if not matching_pattern:
                    continue
                if material in inventory.contents.keys():
                    if inventory.contents[material] >= 0:
                        source_inventory = inventory
                    if (inventory.contents[material] >= quantity and
                        (quantity % inventory.comp_specific_sizes[matching_pattern]['Quantity step'] == 0 or ignore_qty_step)):
                        source_inventory = inventory
                        material_available = True
                        break
                else:
                    # This inventory could potentially be a source for this material, but check max. quantity and quantity step
                    if (inventory.comp_specific_sizes[matching_pattern]['Max. quantity'] >= quantity and
                        (quantity % inventory.comp_specific_sizes[matching_pattern]['Quantity step'] == 0 or ignore_qty_step)):
                        source_inventory = inventory
                        break

        return source_inventory, material_available


    def sort_machines_transport_stationary(self):
        # Sort Machines into transport or stationary
        for mid, machine in self.machines.items():
            if machine.is_transport:
                self.transport_machines.update({mid: TransportMachine(machine_instance=machine)})
            else:
                self.stationary_machines.update({mid: machine})


    def remove_pyqt_signals_from_ops(self):
        # To bypass serialization issues with Ray, erase all pyqtSignals of OperationNodes
        for op_node_objs in self.product_operations.values():
            for op_node in op_node_objs:
                try:
                    delattr(op_node.__class__, 'connect_to_signal')
                    delattr(op_node.__class__, 'clicked_signal')
                    delattr(op_node.__class__, 'disconnect_from_signal')
                    delattr(op_node.__class__, 'moved_signal')
                except AttributeError:
                    # pyqtSignals must have been deleted from the class definition of OperationNode already
                    break
                break
            break


    def processing_time_to_seconds(self):
        # Convert every processing time into seconds once and for all
        for product_id, operation_list in self.product_operations.items():
            for operation_node in operation_list:
                if operation_node.processing_time_unit != 's':
                    processing_time_secs = self.get_int_seconds(operation_node.processing_time_value, operation_node.processing_time_unit)
                    operation_node.processing_time_unit = 's'
                    operation_node.processing_time_value = processing_time_secs


    def set_identical_inventory_sizes(self):
        # Inventory size specifications in case of being identical with buffers
        for inventory_id, inventory in self.inventories.items():
            if inventory.identical_buffer:
                buffer_code_chunks = inventory.identical_buffer.split(" : ")
                ws : Workstation = self.workstations[buffer_code_chunks[0]]
                buff_loc = buffer_code_chunks[1]
                buff_idx1 = buffer_code_chunks[2]
                buff_obj : Buffer = None
                if buff_loc == 'IN':
                    buff_obj = ws.physical_input_buffers[buff_idx1]
                elif buff_loc == 'OUT':
                    buff_obj = ws.physical_output_buffers[buff_idx1]
                inventory.diff_comp_comb = buff_obj.diff_comp_comb
                inventory.sequence_type = buff_obj.sequence_type
                inventory.comp_specific_sizes = buff_obj.comp_specific_sizes


    def prepare_tool_state_tracker(self):
        self.tool_state_tracker = dict()
        for tool_id, tool in self.tools.items():
            prop_val_dict = {}
            for stat_prop, stat_prop_val in tool.static_properties.items():
                prop_val_dict.update({stat_prop: stat_prop_val['Value']})
            for dyn_prop, dyn_prop_val in tool.dynamic_properties.items():
                prop_val_dict.update({dyn_prop: (dyn_prop_val['Min'] + dyn_prop_val['Max']) / 2})
            self.tool_state_tracker.update({tool_id: prop_val_dict})


    def prepare_order_tracker(self):
        # Fill order tracker variables with data
        for order_id, order in self.order_list.order_list.items():
            single_order_data = {}
            product_progress = []
            for product_id, product in order.products.items():
                # For each unique/distinct operation within a customer order reserve a row in the action space matrix
                for operation in self.product_operations[product_id]:
                    self.action_matrix_row_dict.update({operation.operation_name + '|' + product_id + '|' + order_id: self.action_matrix_n_rows})
                    self.action_matrix_n_rows += 1
                    
                # Calculate critical path duration (idea is to use this as a reference for the flow time - a product cannot be made faster than its critical path)
                id_edges = [(edge[0].operation_name, edge[1].operation_name) for edge in self.product_instructions.product_palette[product_id]]
                id_durations = {}
                for operation in self.product_operations[product_id]:
                    id_durations.update({operation.operation_name: operation.processing_time_value})
                    # self.get_int_seconds(operation.processing_time_value, operation.processing_time_unit)
                critical_path_duration = self.product_instructions.critical_path_duration(id_edges, id_durations)

                for instance in range(order.products[product_id]):
                    single_instance_data = {}
                    single_instance_data.update({'product_id': product_id})
                    single_instance_data.update({'product_instance': instance})
                    operation_progress = {}
                    for operation in self.product_operations[product_id]:
                        single_operation_data = {}
                        # Record predecessors of each operation for fast retrieval and precedence constraint checks
                        single_operation_data.update({'predecessors': self.product_instructions.get_predecessor_ids(operation, self.product_instructions.product_palette[product_id])})
                        single_operation_data.update({'location': None})
                        single_operation_data.update({'status': OperationStatus.IN_BACKLOG})
                        single_operation_data.update({'remaining_work': id_durations[operation.operation_name]})
                        single_operation_data.update({'start_time': None})
                        single_operation_data.update({'finish_time': None})
                        operation_progress.update({operation.operation_name: single_operation_data})
                    single_instance_data.update({'operation_progress': operation_progress})
                    single_instance_data.update({'production_end_time': None})
                    single_instance_data.update({'productive_time': None})
                    single_instance_data.update({'critical_path_duration': critical_path_duration})
                    product_progress.append(single_instance_data)
            single_order_data.update({'product_progress': product_progress})
            single_order_data.update({'release_time': int(datetime.strptime(order.release_time, "%d.%m.%Y %H:%M").timestamp())})
            single_order_data.update({'deadline': int(datetime.strptime(order.deadline, "%d.%m.%Y %H:%M").timestamp())})
            self.order_progress.update({order_id: single_order_data})


    def calculate_action_matrix_dimensions(self):
        # Reserve rows for transport machines and 1 row for decision skipping
        for transport_machine in self.transport_machines.keys():
            self.action_matrix_row_dict.update({transport_machine: self.action_matrix_n_rows})
            self.action_matrix_n_rows += 1

        self.action_matrix_row_dict.update({'skip': self.action_matrix_n_rows})
        self.action_matrix_n_rows += 1

        # Reserve columns for workstations, inventories and 1 column for decision skipping
        for workstation in self.workstations.keys():
            self.action_matrix_col_dict.update({workstation: self.action_matrix_n_cols})
            self.action_matrix_n_cols += 1
        
        for inventory in self.inventories.keys():
            self.action_matrix_col_dict.update({inventory: self.action_matrix_n_cols})
            self.action_matrix_n_cols += 1

        self.action_matrix_col_dict.update({'skip': self.action_matrix_n_cols})
        self.action_matrix_n_cols += 1

        # Make reverse dicts for fast lookup of IDs by integer indices of the action matrix
        self.action_matrix_reverse_row_dict = {v: k for k, v in self.action_matrix_row_dict.items()}
        self.action_matrix_reverse_col_dict = {v: k for k, v in self.action_matrix_col_dict.items()}


    def prepare_observation_space_dimensions(self):
        # Calculate how many vector entries will each observed attribute contribute to the observation space size
        N_ord = len(self.order_list.order_list)
        N_P = len(self.product_instructions.product_palette)
        N_ws = len(self.workstations)
        N_sm = len(self.stationary_machines)
        N_tm = len(self.transport_machines)
        N_t = len(self.tools)
        N_tp = len(self.tool_pools)
        N_wp = len(self.worker_pools)
        N_w = len(self.workers)
        K_w = len(self.worker_capabilities)
        N_inv = len(self.inventories)
        N_sb = len(self.supply_behaviours)
        pg = sum([len(v)*len(v) for k,v in self.product_operations.items()])  # entries to encode all product precedence graphs as matrices
        K_m = len(self.machine_capabilities)
        N_op = 0
        for order in self.order_list.order_list.values():
            for product_id, product_quantity in order.products.items():
                N_op += product_quantity * len(self.product_operations[product_id])
        N_ib = 0
        N_ob = 0
        for workstation in self.workstations.values():
            N_ib += len(workstation.physical_input_buffers)
            N_ob += len(workstation.physical_output_buffers)
        
        self.raw_observation_vector_sizes.update({'Workers: location (workstation)': N_w * N_ws})
        self.raw_observation_vector_sizes.update({'Workers: location (transport)': N_w * N_tm})
        self.raw_observation_vector_sizes.update({'Workers: destination (workstation)': N_w * N_ws})
        self.raw_observation_vector_sizes.update({'Workers: destination (transport)': N_w * N_tm})
        self.raw_observation_vector_sizes.update({'Workers: status': N_w * 4})  # because 4 different stati possible
        #self.raw_observation_vector_sizes.update({'Worker-pool assignment': N_w * N_wp})
        #self.raw_observation_vector_sizes.update({'Tool-pool assignment': N_t * N_tp})
        self.raw_observation_vector_sizes.update({'Tools: location': N_t * N_ws})
        self.raw_observation_vector_sizes.update({'Tools: status': N_t * 3})  # seized / permanent / in use
        self.raw_observation_vector_sizes.update({'Workstations: status': N_ws * 11})  # because 11 different stati possible
        self.raw_observation_vector_sizes.update({'Input buffers: fill level': N_ib})  # relative to maximum capacity
        self.raw_observation_vector_sizes.update({'Output buffers: fill level': N_ob})  # relative to maximum capacity
        self.raw_observation_vector_sizes.update({'Operations: location (workstation)': N_op * N_ws})
        self.raw_observation_vector_sizes.update({'Operations: remaining work': 0})  # encoded by replacing the 1 in location assignment by relative remaining work
        self.raw_observation_vector_sizes.update({'Operations: timeliness': N_op * 3})  # start time, remaining time in order, order deadline

        self.agg_observation_vector_sizes.update({'Buffers: average fill level': N_ib + N_ob})  # from simulation start onwards
        self.agg_observation_vector_sizes.update({'Buffers: fill level variability': N_ib + N_ob})  # from simulation start onwards
        self.agg_observation_vector_sizes.update({'Workstations: productive time ratio': N_ws})  # from simulation start onwards: how much time status = BUSY (Hauptnutzung)
        self.agg_observation_vector_sizes.update({'Workstations: setup time ratio': N_ws})  # from simulation start onwards: how much time status = SETUP (Nebennutzung)
        self.agg_observation_vector_sizes.update({'Workers: productive time ratio': N_w})  # from simulation start onwards: how much time status = BUSY (Haupttätigkeit)
        self.agg_observation_vector_sizes.update({'Workers: setup time ratio': N_w})  # from simulation start onwards: how much time status = SETTING_UP (Haupttätigkeit - Rüsten)
        self.agg_observation_vector_sizes.update({'Workers: walking time ratio': N_w})  # from simulation start onwards: how much time status = WALKING (Nebentätigkeit)
        self.agg_observation_vector_sizes.update({'Transport machines: material flow time ratio': N_tm})  # from simulation start onwards: how much time status = EXECUTING_TRANSPORT
        # Next KPI tells how short is the product's critical path compared to the time spent from the first operation till product is made
        self.agg_observation_vector_sizes.update({'Products: critical path duration / flow time': N_P})  # from simulation start onwards: 1.0 if prod. time < CPD, afterwards CPD/PT


    def make_simulatable(self):
        '''
        Prepares all transformations from input configuration into a simulatable object.
        Use functions from within to recalculate specific parameters.
        '''

        # TODO If available, load a starting system state for realistic simulation usage

        self.sort_machines_transport_stationary()

        # Prepare product operations
        self.product_operations = self.product_instructions.get_product_operations()

        # Prepare product palette to be serializable (get rid of QLabel subclass OperationNodes)
        self.product_instructions.clean_from_qt()

        self.remove_pyqt_signals_from_ops()
        
        self.processing_time_to_seconds()

        # Prepare raw material names
        self.raw_material_names = self.product_instructions.get_raw_material_names()

        self.set_identical_inventory_sizes()

        # Prepare helper lists of workstations' possible provided capabilities, tools and materials
        for workstation in self.workstations.values():
            self.find_potential_capabilities(workstation)
            self.find_potential_tools(workstation)
            self.find_potential_materials(workstation)

        # Prepare tool pools, worker pools and tool state tracker variables
        self.worker_pool_tracker = deepcopy(self.worker_pools)
        self.tool_pool_tracker = deepcopy(self.tool_pools)

        self.prepare_tool_state_tracker()

        self.prepare_order_tracker()

        self.calculate_action_matrix_dimensions()

        # Set the dimensions of action matrix
        self.action_matrix = numpy.zeros((self.action_matrix_n_rows, self.action_matrix_n_cols), dtype="int32")

        self.prepare_observation_space_dimensions()

        self.is_prepared = True


    def eligible_workstations_for_operation(self, operation):
        '''Returns IDs of all workstations technically eligible to commit to a given operation.
        '''
        # Finding eligible workstations consists of the following steps:
        # 1. Workstation can provide necessary capabilities
        # 2. Workstation can provide necessary tools
        # 3. Workstation's physical input buffers can contain the required components in necessary amounts
        eligible_workstations = []
        for workstation_id, workstation in self.workstations.items():
            capabilities_possible = set(operation.capabilities).issubset(workstation.potential_capabilities)
            tools_possible = set(operation.tools.keys()).issubset(workstation.potential_tools)
            materials_possible_checklist = []
            for material, quantity in operation.components.items():
                material_fits = False
                # Search whether the workstation supports this material
                for supp_mat, max_qty in workstation.potential_materials.items():
                    if self.material_matches_wildcard(material, supp_mat) or material == supp_mat:
                        if quantity <= max_qty:
                            material_fits = True
                            break
                materials_possible_checklist.append(material_fits)
            materials_possible = all(materials_possible_checklist)
            if all([capabilities_possible, tools_possible, materials_possible]):
                eligible_workstations.append(workstation_id)
        return eligible_workstations
    

    def find_operation_by_name(self, operation_name, operation_list):
        for op in operation_list:
            if op.operation_name == operation_name:
                return op


    def is_manual_operation(self, operation_id, product_id):
        '''
        Returns True if the operation doesn't require any machine capabilities, False otherwise
        '''
        operation = self.find_operation_by_name(operation_id, self.product_operations[product_id])
        for capability in operation.capabilities:
            if capability in self.machine_capabilities:
                return False
        return True
    

    def get_operation_state(self, operation_id : str, product_id : str, instance_idx : int, order_id : str):
        '''
        Returns a dictionary describing current state of an operation specified by four indices
        from the order_progress variable of the production system.
        This dictionary can be later parsed to get specific information about operation state.
        '''
        product_progress : list = self.order_progress[order_id]['product_progress']
        matching_instance = None
        for instance in product_progress:
            if instance['product_id'] == product_id and instance['product_instance'] == instance_idx:
                matching_instance = instance
                break
        return matching_instance['operation_progress'][operation_id]
    

    def required_tools_at_workstation(self, operation_id, product_id, workstation : Workstation):
        '''
        Returns a tuple with two values:
        1. True if all tools required for this operation are available at the workstation (permanent, seized or in use), False otherwise.
        2. Dictionary of tools {tool_id: {property: {Min, Max, Unit, a, b, c}}} that are missing at this workstation to start executing the operation.
        '''
        operation = self.find_operation_by_name(operation_id, self.product_operations[product_id])

        all_tools_available = True
        missing_tools = dict()

        for tool_id, req_eff_table in operation.tools.items():
            if all([tool_id not in workstation.permanent_tools,
                   tool_id not in workstation.seized_tools,
                   tool_id not in workstation.tools_in_use]):
                all_tools_available = False
                missing_tools.update({tool_id: req_eff_table})
                # for property, req_eff_table in operation.tools[tool_id].items():
                #     property_item = {property: req_eff_table}
                #     missing_tools.update({tool_id: property_item})
        return all_tools_available, missing_tools
    

    def required_tools_in_use(self, operation_id, product_id, workstation : Workstation):
        '''
        Returns a tuple with three values:
        1. True if all tools required for this operation are in the "in use" of the workstation and False otherwise.
        2. List of tool IDs that still need to be put "in use", i.e. need to be setup.
        3. List of tool IDs that are already "in use" but still require setup effort to adjust their dynamic properties.
        '''
        operation = self.find_operation_by_name(operation_id, self.product_operations[product_id])

        all_tools_in_use = True
        tools_to_put_in_use = list()
        tools_needing_property_setup = list()

        for tool_id in operation.tools.keys():
            if tool_id not in workstation.tools_in_use:
                all_tools_in_use = False
                tools_to_put_in_use.append(tool_id)
            if tool_id in workstation.tools_in_use:
                # Check all properties (static and dynamic)
                for property_name, current_value in self.tool_state_tracker[tool_id].items():
                    req_eff_table = operation.tools[tool_id][property_name]
                    if current_value < req_eff_table['Min'] or current_value > req_eff_table['Max']:
                        tools_needing_property_setup.append(tool_id)
                        break
                
        return all_tools_in_use, tools_to_put_in_use, tools_needing_property_setup


    def required_worker_at_workstation(self, operation_id, product_id, workstation : Workstation):
        '''
        Returns a tuple with two values:
        1. True if a worker is present at the workstation and provides all capabilities necessary for this operation , False otherwise.
        2. Entire list of worker capabilities required by this operation.
        '''
        operation = self.find_operation_by_name(operation_id, self.product_operations[product_id])
        worker_at_workstation = True
        all_required_worker_capabilities = []

        if workstation.seized_worker == '':
            worker_at_workstation = False
        else:
            # There is some worker at the workstation, but we need to check their provided capabilities
            for capability in operation.capabilities:
                if capability in self.worker_capabilities:
                    if capability not in self.workers[workstation.seized_worker].provided_capabilities:
                        worker_at_workstation = False
                        break

        if not worker_at_workstation:
            all_required_worker_capabilities = [capability for capability in operation.capabilities if capability in self.worker_capabilities]
                
        return worker_at_workstation, all_required_worker_capabilities
    

    def product_fits_into_workstation_output(self, operation_id, product_id, workstation : Workstation):
        '''
        Returns True if operation's product fits into any physical output buffer (PhOB) of the workstation, False otherwise.
        '''
        fits = False

        operation = self.find_operation_by_name(operation_id, self.product_operations[product_id])

        # TODO In case of batch workstation, it is necessary to check product_fits_into_output
        # of all operations with same operation_id and product_id in wip_operations
        operation_product = (operation.output_name, 1)
        if workstation.machine:
            if self.machines[workstation.machine].batch_processing:
                out_qty = 0
                for op in workstation.wip_operations:
                    if op[0] == operation_id and op[1] == product_id:
                        out_qty += 1
                operation_product = (operation.output_name, out_qty)

        for phob in workstation.physical_output_buffers.values():
            if phob.accepts_objects(operation_product):
                fits = True
                break
        return fits


    def get_dynamic_tool_property_after_operation(self, operation_node, tool_id, property_name, start_value):
        req_eff_table = operation_node.tools[tool_id][property_name]
        a = req_eff_table['a']
        b = req_eff_table['b']
        c = req_eff_table['c']
        return start_value + a * math.pow(start_value, b) + c


    def apply_workstation_sequencing_heuristic(self, workstation_id, op_triple_list, heuristic):
        '''
        Applies a workstation sequencing heuristic and directly calls set_action(), bypassing get_legal_actions().
        Gets called from push_operation_downstream() if WORKSTATION_SEQUENCING is configured to be handled by a heuristic.
        '''
        # To prevent any stochasticity here
        op_triple_list = sorted(op_triple_list)

        # The "skip" option is not supported by heuristics.
        # Also note that postponed workstation sequencing doesn't provide "skip" as an option.
        if ('skip', None, None) in op_triple_list:
            op_triple_list.remove(('skip', None, None))

        chosen_op_triple = ()

        # Vector of alternative operation durations in seconds to enable LPT and SPT
        op_durations = []
        # Vector of deadlines to enable EDF
        ord_deadlines = []
        # Vector of numbers of remaining operations to finish the product to enable LOR and MOR
        prod_remaining_ops = []

        for op_triple in op_triple_list:
            operation_id = op_triple[0]
            product_id = op_triple[1]
            order_id = op_triple[2]
            for instance_data in self.order_progress[order_id]['product_progress']:
                if instance_data['product_id'] == product_id:
                    if instance_data['operation_progress'][operation_id]['status'] == OperationStatus.ASSIGNED:
                        remaining_work = instance_data['operation_progress'][operation_id]['remaining_work']
                        order_deadline = self.order_progress[order_id]['deadline']
                        n_remaining_ops = 0
                        for op_id, op_info_dict in instance_data['operation_progress'].items():
                            if op_info_dict['remaining_work'] > 0:
                                n_remaining_ops += 1
                        op_durations.append(remaining_work)
                        ord_deadlines.append(order_deadline)
                        prod_remaining_ops.append(n_remaining_ops)
                        break

        if heuristic == 'FIFO':
            chosen_op_triple = op_triple_list[0]

        if heuristic == 'Longest processing time (LPT)':
            chosen_op_triple = op_triple_list[numpy.argmax(op_durations)]

        if heuristic == 'Shortest processing time (SPT)':
            chosen_op_triple = op_triple_list[numpy.argmin(op_durations)]

        if heuristic == 'Earliest deadline first (EDF)':
            chosen_op_triple = op_triple_list[numpy.argmin(ord_deadlines)]

        if heuristic == 'Least operations remaining (LOR)':
            chosen_op_triple = op_triple_list[numpy.argmin(prod_remaining_ops)]

        if heuristic == 'Most operations remaining (MOR)':
            chosen_op_triple = op_triple_list[numpy.argmax(prod_remaining_ops)]

        if heuristic == 'Random':
            chosen_op_triple = op_triple_list[numpy.random.choice(range(len(op_triple_list)))]

        op_str = chosen_op_triple[0] + '|' + chosen_op_triple[1] + '|' + chosen_op_triple[2]
        i = self.action_matrix_row_dict[op_str]
        j = self.action_matrix_col_dict[workstation_id]
        action_int = i * self.action_matrix_n_cols + j
        self.set_action(action_int)

        # self.required_action_type = None --> actually happens in set_action() anyway


    def apply_workstation_routing_heuristic(self, op_quadruple, eligible_workstations, heuristic):
        '''
        Applies a workstation routing heuristic and directly calls set_action(), bypassing get_legal_actions().
        Gets called from push_operation_downstream() if WORKSTATION_ROUTING is configured to be handled by a heuristic.
        '''
        # To prevent any stochasticity here
        eligible_workstations = sorted(eligible_workstations)

        chosen_workstation = ''

        # Vector of numbers of queued operations at workstations to enable LQO
        queued_ops = []
        # Vector of numbers of queued and currently processed operations at workstations to enable LQPO
        queued_and_processed_ops = []
        # Vector of queued time at workstations to enable LQT
        queued_times = []

        for workstation_id in eligible_workstations:
            workstation : Workstation = self.workstations[workstation_id]
            queued_ops.append(len(workstation.input_operation_buffer))
            queued_and_processed_ops.append(len(workstation.input_operation_buffer) + len(workstation.wip_operations))
            queued_time = 0.0
            for op_quad in workstation.input_operation_buffer:
                op_id = op_quad[0]
                prod_id = op_quad[1]
                op = self.find_operation_by_name(op_id, self.product_operations[prod_id])
                queued_time += op.processing_time_value
            queued_times.append(queued_time)

        if heuristic == 'Least queued operations (LQO)':
            chosen_workstation = eligible_workstations[numpy.argmin(queued_ops)]

        if heuristic == 'Least queued and processed operations (LQPO)':
            chosen_workstation = eligible_workstations[numpy.argmin(queued_and_processed_ops)]

        if heuristic == 'Least queued time (LQT)':
            chosen_workstation = eligible_workstations[numpy.argmin(queued_times)]

        if heuristic == 'Random':
            chosen_workstation = eligible_workstations[numpy.random.choice(range(len(eligible_workstations)))]

        i = self.action_matrix_row_dict[op_quadruple[0] + '|' + op_quadruple[1] + '|' + op_quadruple[2]]
        j = self.action_matrix_col_dict[chosen_workstation]
        action_int = i * self.action_matrix_n_cols + j
        self.set_action(action_int)


    def push_operation_downstream(self, operation_id, product_id, order_id, product_instance, eligible_workstations, operation_progress, postponed=False):
        '''
        Returns True if the operation was pushed to a downstream workstation or a routing decision is needed.
        Raises a RuntimeError if there are no eligible workstations to execute the operation.
        '''
        print(f'Pushing (introducing) operation {operation_id}|{product_id}|{order_id}|{str(product_instance)} into production system')
        
        if len(eligible_workstations) == 0:
            print(f'There are no eligible workstations for {operation_id} of {product_id}!')
            raise RuntimeError
        
        if len(eligible_workstations) == 1:
            # If there is technically only one
            # eligible workstation for this operation,
            # the routing action is trivial and is handled
            # by the simulation itself and not by the planning algorithm.
            # Or the sequencing decision has already been made.
            ws : Workstation = self.workstations[eligible_workstations[0]]

            if not postponed:
                ws.input_operation_buffer.append((operation_id, product_id, order_id, product_instance))
                operation_progress[operation_id]['location'] = eligible_workstations[0]
                operation_progress[operation_id]['status'] = OperationStatus.ASSIGNED

            if not postponed:
                # Generate MaterialsRequest
                component_dict = deepcopy(self.find_operation_by_name(operation_name=operation_id, operation_list=self.product_operations[product_id]).components)
                self.event_queue.append(MaterialsRequest(timestamp=self.timestamp, component_dict=component_dict, target_workstation=ws))

            # If the workstation currently has operations in its operation WIP,
            # then it makes sense to postpone the sequencing decision (unless there is batch processing).
            # TODO: When doing postponed sequencing, should wip_operations be empty?
            if len(ws.wip_operations) > 0:
                if ws.machine:
                    if self.machines[ws.machine].batch_processing:
                        # Don't postpone sequencing, try completing the batch
                        pass
                    elif not self.machines[ws.machine].batch_processing:
                        self.required_action_type = None
                        self.event_queue.appendleft(WorkstationSequencingPostponed(timestamp=self.timestamp, workstation=ws))
                        return True

            # Make a list of alternative operations to choose from - including "skip" option if not postponed
            if not postponed:
                operation_alternatives = [('skip', None, None)]
            else:
                operation_alternatives = []

            # Check whether the WS has any PhIB that are not "free sequence"
            forced_sequence_buffer = None
            for buffer in ws.physical_input_buffers.values():
                if buffer.sequence_type == BufferSequenceType.FIFO or buffer.sequence_type == BufferSequenceType.LIFO:
                    forced_sequence_buffer = buffer
                    break
                if buffer.sequence_type == BufferSequenceType.SOLID_RAW_MATERIAL:
                    raise NotImplementedError()
                
            forced_alternative_found = False

            for released_op in ws.input_operation_buffer:
                # If there is at least one PhIB that is not "free sequence", make sure that the only operation alternative
                # we record is the operation that is forced by such buffer
                if forced_alternative_found:
                    break
                if forced_sequence_buffer is None:
                    operation_alternatives.append((released_op[0], released_op[1], released_op[2]))
                    continue
                if forced_sequence_buffer is not None:
                    # Check if it's empty
                    buffer_empty = True
                    for k, v in forced_sequence_buffer.contents.items():
                        if v > 0:
                            buffer_empty = False
                            break
                    if buffer_empty:
                        # While such a buffer is empty, there is still chance to commit to operations free of sequence
                        operation_alternatives.append((released_op[0], released_op[1], released_op[2]))
                        continue
                    # Get the component that is next in the forced sequence buffer
                    next_forced_component = None
                    if forced_sequence_buffer.sequence_type == BufferSequenceType.FIFO:
                        next_forced_component = list(forced_sequence_buffer.contents.items())[0][0]
                    if forced_sequence_buffer.sequence_type == BufferSequenceType.LIFO:
                        next_forced_component = list(forced_sequence_buffer.contents.items())[-1][0]
                    if forced_sequence_buffer.sequence_type == BufferSequenceType.SOLID_RAW_MATERIAL:
                        raise NotImplementedError()
                    # Get the operation that requires this component
                    op_nodes = self.product_operations[released_op[1]]
                    req_matching_op = None
                    for op_node in op_nodes:
                        if next_forced_component in op_node.components.keys():
                            req_matching_op = op_node.operation_name
                            operation_alternatives.append((req_matching_op, released_op[1], released_op[2]))
                            forced_alternative_found = True
                            break

            operation_alternatives = sorted(list(set(operation_alternatives)))  # different product instances within the same order are treated the same (condensed)
            self.required_action_type = ActionType.WORKSTATION_SEQUENCING
            self.action_relevant_info = (eligible_workstations[0], operation_alternatives)

            # Apply a heuristic if so configured
            if self.action_config['Workstation sequencing'][0] == False:  # indirect action
                self.apply_workstation_sequencing_heuristic(workstation_id=self.action_relevant_info[0],
                                                            op_triple_list=self.action_relevant_info[1],
                                                            heuristic=self.action_config['Workstation sequencing'][1])

            # Exit run_until_decision_point() back to set_action(), which will set the operation status to COMMITTED if the operation is chosen
            return True
        
        if len(eligible_workstations) > 1:
            # Workstation routing action required
            self.required_action_type = ActionType.WORKSTATION_ROUTING
            released_op = (operation_id, product_id, order_id, product_instance)
            self.action_relevant_info = (released_op, eligible_workstations)

            # Apply a heuristic if so configured
            if self.action_config['Workstation routing'][0] == False:  # indirect action
                self.apply_workstation_routing_heuristic(op_quadruple=self.action_relevant_info[0],
                                                         eligible_workstations=self.action_relevant_info[1],
                                                         heuristic=self.action_config['Workstation routing'][1])

            # set_action() will change the status of the chosen operation to ASSIGNED 
            return True


    def handle_workstation_sequencing_skip(self, workstation : Workstation):
        '''
        This function can be used to treat any situations when the resources like tools or workers should be released back in the system,
        especially if these resources are shared between workstations/machines.
        '''
        
        # Tools currently in use are put back to their tool pools of origin
        if workstation.machine:
               #WorkstationStatus.BUSY not in workstation.status,
               #WorkstationStatus.SETUP not in workstation.status]):
            machine = self.stationary_machines[workstation.machine]
            machine_setup_matrix = machine.setup_matrix
            hardware_setup_time_unit = machine.hardware_setup_time_unit
            for current_tool in workstation.tools_in_use:
                tool_removal_duration = self.get_int_seconds(machine_setup_matrix[current_tool]['No tool'], hardware_setup_time_unit)
                self.event_queue.append(ToolReleaseEvent(timestamp=self.timestamp + tool_removal_duration,
                                                         workstation=workstation,
                                                         tool=self.tools[current_tool]))
                
        # Releasing workers back into the system
        if workstation.seized_worker:
            self.event_queue.append(WorkerReleaseEvent(timestamp=self.timestamp,
                                                       workstation=workstation,
                                                       worker=self.workers[workstation.seized_worker]))


    def work_on_operation(self, operation_id, product_id, order_id, product_instance, operation_progress, workstation : Workstation, batch_complete=True, auto_setup=False):
        '''
        Gets called once an operation's status is changed to COMMITTED and returns True if the program can continue working on the event queue,
        i.e. all relevant resource requests and other events regarding this operation have been created.
        It is a separate function because many event types lead to this part of the simulation logic.
        '''

        print(f'\nTrying to process operation {operation_id}|{product_id}|{order_id}|{product_instance} at workstation {workstation.workstation_id}...')

        # Are all components needed for this operation available in the workstation's physical input buffers or in the physical WIP?
        required_components = {}  # key: component name, value: quantity
        operation_node = self.find_operation_by_name(operation_id, self.product_operations[product_id])
        required_components = operation_node.components
        all_components_available = True
        available_components = {}  # key: component name, value: quantity
        components_available_in_phib = {}

        # Look in the PhIBs of WS
        for phib in workstation.physical_input_buffers.values():
            # If empty, no need to check
            buffer_empty = True
            for k, v in phib.contents.items():
                if v > 0:
                    buffer_empty = False
                    break
            if buffer_empty:
                continue
            if phib.sequence_type == BufferSequenceType.FIFO:
                next_forced_component = list(phib.contents.items())[0][0]
                next_forced_quantity = list(phib.contents.items())[0][1]
            if phib.sequence_type == BufferSequenceType.LIFO:
                next_forced_component = list(phib.contents.items())[-1][0]
                next_forced_quantity = list(phib.contents.items())[-1][1]
            if phib.sequence_type == BufferSequenceType.FIFO or phib.sequence_type == BufferSequenceType.LIFO:
                if next_forced_component not in available_components.keys():
                    available_components.update({next_forced_component: next_forced_quantity})
                    components_available_in_phib.update({next_forced_component: next_forced_quantity})
                else:
                    available_components[next_forced_component] += next_forced_quantity
                    components_available_in_phib[next_forced_component] += next_forced_quantity
            if phib.sequence_type == BufferSequenceType.SOLID_RAW_MATERIAL:
                raise NotImplementedError()
            if phib.sequence_type == BufferSequenceType.FREE:
                for k,v in phib.contents.items():
                    if k not in available_components.keys():
                        available_components.update({k: v})
                        components_available_in_phib.update({k: v})
                    else:
                        available_components[k] += v
                        components_available_in_phib[k] += v
        
        # Look in the Ph-WIP (wip_components) of WS
        # But first erase empty entries
        workstation.wip_components = [entry for entry in workstation.wip_components if entry['Quantity'] > 0]
        for dict in workstation.wip_components:
            ac = dict['Component']
            aq = dict['Quantity']
            if ac not in available_components.keys():
                available_components.update({ac: aq})
            else:
                available_components[ac] += aq

        # Check availability and record what is still missing
        missing_components = {}  # key: name, value: quantity
        for rc,rq in required_components.items():
            if rc not in available_components.keys():
                all_components_available = False
                missing_components.update({rc: rq})
                continue
            if rq > available_components[rc]:
                all_components_available = False
                if rc in missing_components.keys():
                    missing_components[rc] += rq - available_components[rc]
                else:
                    missing_components.update({rc: rq})

        if not all_components_available:
            print('    Not all of the required components are at the workstation.')
            if WorkstationStatus.WAITING_FOR_MATERIAL not in workstation.status:
                workstation.status.append(WorkstationStatus.WAITING_FOR_MATERIAL)
                print('    Added WAITING_FOR_MATERIAL to the workstation status list.')
                workstation.log_status_change(self.timestamp)
            # Note: MaterialsRequests should be generated already when an operation has been routed to a workstation,
            # not when it's sequenced (that would be very inefficient)!
            # for k,v in missing_components.items():
            #     self.event_queue.append(MaterialsRequest(timestamp=self.timestamp, component_dict={k:v}, target_workstation=workstation))

        if all_components_available:
            print('    All required components are at the workstation.')
            print('    Moving all required components from PhIBs into Ph-WIP.')
            # Move all required components that are still in PhIBs, into Ph-WIP (wip_components)
            # See what is already in the wip_components
            components_available_in_wip = {}
            for d in workstation.wip_components:
                components_available_in_wip.update({d['Component']: d['Quantity']})
            # Write down what still needs to be moved from PhIB
            components_to_take_from_phib = {}
            for rc,rq in required_components.items():
                if rc not in components_available_in_wip.keys():
                    components_to_take_from_phib.update({rc: rq})
                    continue
                if rq > components_available_in_wip[rc]:
                    components_to_take_from_phib[rc] += rq - components_available_in_wip[rc]
            # Move it into Ph-WIP
            for mc,mq in components_to_take_from_phib.items():
                already_moved_qty = 0
                phib_idx = 0
                # Find or create an entry for components to be moved
                component_type_already_in = False
                for d in workstation.wip_components:
                    if d['Component'] == mc:
                        component_type_already_in = True
                        break
                if not component_type_already_in:
                    workstation.wip_components.append({'Component': mc, 'Quantity': 0})
                while already_moved_qty < mq:
                    phib = list(workstation.physical_input_buffers.values())[phib_idx]
                    if mc in phib.contents.keys():
                        #if phib.sequence_type == BufferSequenceType.FREE:
                        # TODO (Check): moving components from buffers into Ph-WIP seems to be independent from
                        # buffer sequence type because get_legal_actions() already makes sure that only
                        # sequencing actions that respect buffer sequence constraints are presented to the agent.
                        if mq - already_moved_qty > phib.contents[mc]:
                            already_moved_qty += phib.contents[mc]
                            phib.contents.pop(mc)
                            phib.log_fill_level_change(self.timestamp)
                            for d in workstation.wip_components:
                                if d['Component'] == mc:
                                    d['Quantity'] += already_moved_qty
                                    break
                        else:
                            phib.contents[mc] -= mq - already_moved_qty
                            phib.log_fill_level_change(self.timestamp)
                            already_moved_qty = mq
                            for d in workstation.wip_components:
                                if d['Component'] == mc:
                                    d['Quantity'] = mq
                                    break
                    phib_idx += 1

            # Since some components have been moved from PhIB to Ph-WIP,
            # this is a good point to retry unloading any IDLE transport machine
            # currently waiting at the workstation.
            for tm in self.transport_machines.values():
                if all([tm.current_location == workstation.workstation_id,
                        TransportMachineStatus.IDLE in tm.status,
                        TransportMachineStatus.UNLOADING in tm.status]):
                    print('    Retrying to unload an IDLE transport machine waiting at the workstation...')
                    # Find what was the source of the material (basically an identifier of transport orders)
                    ms = ''
                    for to in tm.transport_order_list:
                        if to['Destination'] == tm.current_location and to['Commitment'] == True:
                            ms = to['Source']
                            break
                    self.execute_transport_order(material_source=ms, transport_machine=tm)

            if WorkstationStatus.WAITING_FOR_MATERIAL in workstation.status:
                # Retrigger any pending RawMaterialArrivalEvents and MaterialsArrivalEvents at this workstation
                for _e in self.event_queue:
                    if isinstance(_e, RawMaterialArrivalEvent):
                        _inv = _e.inventory
                        if _inv.identical_buffer.split(" : ")[0] == workstation.workstation_id:
                            print(f'    Marked a pending RawMaterialArrivalEvent at inventory {_inv.inventory_id} for retry (identical buffer of this workstation).')
                            _e.rmi_overflow = False
                            break
                    if isinstance(_e, MaterialsArrivalEvent):
                        _ws = _e.workstation
                        if _ws.workstation_id == workstation.workstation_id:
                            print(f'    Marked a pending MaterialsArrivalEvent at this workstation for retry.')
                            _e.buffer_overflow = False
                            break
                # Remove "waiting for material" status
                workstation.status.remove(WorkstationStatus.WAITING_FOR_MATERIAL)
                print(f'    Removed WAITING_FOR_MATERIAL from the status list of workstation {workstation.workstation_id}.')
                workstation.log_status_change(self.timestamp)

        # Handle tool, worker, setup and output capacity requirements

        # Helper variables
        operation_is_fully_manual = self.is_manual_operation(operation_id, product_id)
        all_tools_at_workstation, missing_tools = self.required_tools_at_workstation(operation_id, product_id, workstation)
        all_tools_in_use, tools_to_put_in_use, tools_needing_property_setup = self.required_tools_in_use(operation_id, product_id, workstation)
        worker_at_workstation, all_required_worker_capabilities = self.required_worker_at_workstation(operation_id, product_id, workstation)
        product_fits_into_output = self.product_fits_into_workstation_output(operation_id, product_id, workstation)

        # Request missing tools
        if not all_tools_at_workstation:
            print('    Not all required tools are at the workstation.')
            if WorkstationStatus.WAITING_FOR_TOOLS not in workstation.status:
                print('    The workstation has not requested tools for this operation yet.')
                self.event_queue.append(ToolsRequest(timestamp=self.timestamp, tools=missing_tools, target_workstation=workstation))
                workstation.status.append(WorkstationStatus.WAITING_FOR_TOOLS)
                print('    Added WAITING_FOR_TOOLS to workstation status list.')
                workstation.log_status_change(self.timestamp)

        # Request worker capabilities
        #if all([operation_is_fully_manual, not worker_at_workstation]) or all([not operation_is_fully_manual, all_tools_in_use, not worker_at_workstation]):
        if not worker_at_workstation:
            print('    No worker is currently present at the workstation.')
            # Workers are required for operation execution or tool setup.
            # In case of operation execution, certain worker capabilities will be requested (non-empty list).
            # In case of tool setup the assumption is to get any worker from allowed worker pools.
            # The list of requested capabilities will be empty, but there will still be a WorkerCapabilitiesRequest in the gloabl event queue.
            # Attention needs to be paid to batch operations: no need to generate a request for each operation in the batch!
            if WorkstationStatus.WAITING_FOR_WORKER not in workstation.status:
                if all_required_worker_capabilities == []:
                    if all_tools_in_use and len(tools_needing_property_setup) == 0:
                        print('    Setup operations have already been executed or are not required.')
                    else:
                        print('    Tool setup needs to be executed.')
                        #print('    The workstation has not requested worker capabilities for this operation yet.')
                        # If the workstation hasn't already requested a worker...
                        # and if the workstation has access to any worker pools...
                        if not auto_setup:
                            self.event_queue.append(WorkerCapabilitiesRequest(timestamp=self.timestamp,
                                                                              capability_list=all_required_worker_capabilities,
                                                                              target=workstation))
                            workstation.status.append(WorkstationStatus.WAITING_FOR_WORKER)
                            print('    Added WAITING_FOR_WORKER to workstation status list.')
                            workstation.log_status_change(self.timestamp)
                        else:
                            print('    This station does not have access to any worker pools - assuming automated setup capabilities.')
                else:
                    print('    Some specific worker capabilities during operation execution are needed (not setup).')
                    self.event_queue.append(WorkerCapabilitiesRequest(timestamp=self.timestamp, capability_list=all_required_worker_capabilities, target=workstation))
                    workstation.status.append(WorkstationStatus.WAITING_FOR_WORKER)
                    print('    Added WAITING_FOR_WORKER to workstation status list.')
                    workstation.log_status_change(self.timestamp)

        # Execute any necessary and possible setup operations
        if all([all_tools_at_workstation,
               WorkstationStatus.WAITING_FOR_WORKER not in workstation.status,
               WorkstationStatus.SETUP not in workstation.status,
               WorkstationStatus.BUSY not in workstation.status]):
            print('    All tools are at workstation; not WAITING_FOR_WORKER; not SETUP; not BUSY.')
            
            if WorkstationStatus.WAITING_FOR_TOOLS in workstation.status:
                workstation.status.remove(WorkstationStatus.WAITING_FOR_TOOLS)
                print(f'    Removed WAITING_FOR_TOOLS from the status list of workstation {workstation.workstation_id}.')
                workstation.log_status_change(self.timestamp)

            # Calculate total setup duration for putting the tools "in use" and also adjusting their dynamic properties if they have such.
            total_setup_duration = 0

            if not all_tools_in_use:
                # Get the machine setup matrix if it is not a fully manual operation
                machine_setup_matrix = {}
                machine_tool_slots = {}
                hardware_setup_time_unit = ''
                hardware_setup_parallel_to_operation = False
                software_setup_time_value = 0.0
                software_setup_time_unit = ''
                software_setup_parallel_to_operation = False
                if not operation_is_fully_manual:
                    machine = self.stationary_machines[workstation.machine]
                    machine_setup_matrix = machine.setup_matrix
                    machine_tool_slots = machine.tool_slots
                    hardware_setup_time_unit = machine.hardware_setup_time_unit
                    hardware_setup_parallel_to_operation = machine.hardware_setup_parallel_to_operation
                    software_setup_time_value = machine.software_setup_time_value
                    software_setup_time_unit = machine.software_setup_time_unit
                    software_setup_parallel_to_operation = machine.software_setup_parallel_to_operation
                # Add software setup time if not parallel to operation
                if not software_setup_parallel_to_operation:
                    total_setup_duration += self.get_int_seconds(software_setup_time_value, software_setup_time_unit)
                # Add hardware setup time if not parallel to operation
                if not hardware_setup_parallel_to_operation:
                    # Calculate how long it takes to put all tools into "in use" of the workstation based on the workstation's machine setup matrix
                    tool_exchange_duration = 0
                    for tool_id in tools_to_put_in_use:
                        target_tool_slot = machine_tool_slots[tool_id]
                        # Find what tool is currently in tools_in_use and also occupying the same slot as the tool we want to setup
                        tool_to_exchange = ''
                        for current_tool in workstation.tools_in_use:
                            if machine_tool_slots[current_tool] == target_tool_slot:
                                tool_to_exchange = current_tool
                                break
                        if tool_to_exchange == '':
                            tool_to_exchange = 'No tool'
                        try:
                            tool_exchange_duration += self.get_int_seconds(machine_setup_matrix[tool_to_exchange][tool_id], hardware_setup_time_unit)
                        except KeyError:
                            print('Warning: unknown setup duration, defaulting to 0.')
                    # For the case that some tool slot is currently occupied but gets empty after setup
                    currently_occupied_tool_slots = [machine_tool_slots[t] for t in workstation.tools_in_use]
                    tool_slots_to_be_used = [machine_tool_slots[t] for t in operation_node.tools.keys()]
                    for current_tool in workstation.tools_in_use:
                        if machine_tool_slots[current_tool] not in tool_slots_to_be_used:
                            tool_exchange_duration += self.get_int_seconds(machine_setup_matrix[current_tool]['No tool'], hardware_setup_time_unit)
                    total_setup_duration += tool_exchange_duration

                # Actually put the tools "in use" to block them from being seized by other workstations or workers
                workstation.tools_in_use = list(operation_node.tools.keys())
                print(f'    Tools in use after setup (future state): {str(workstation.tools_in_use)}')
                workstation.seized_tools = [tid for tid in workstation.seized_tools if tid not in workstation.tools_in_use]
                print(f'    Seized tools after setup (future state): {str(workstation.seized_tools)}')

            # Note: dynamic property adjustment happens once tools are put "in use", not before that.
            _, _, tools_needing_property_setup = self.required_tools_in_use(operation_id, product_id, workstation)
            if len(tools_needing_property_setup) > 0:
                print('    Some tools require property setup.')
                # Do tool property setup, apply specified setup costs
                for tool_id in workstation.tools_in_use:
                    if tool_id not in tools_needing_property_setup:
                        continue
                    # Check whether properties are in accepted requirement intervals and do setup if not
                    for property_name, current_value in self.tool_state_tracker[tool_id].items():
                        req_eff_table = operation_node.tools[tool_id][property_name]
                        # If a dynamic property is outside of the specified requirement interval,
                        # and the operation effect goes into the same direction,
                        # reset the property to the opposite extremum.
                        # If the effect goes in the opposite direction,
                        # just reset the property to the closest extremum.
                        limit_name_dict = {-1: 'Min',
                                           1: 'Max'}
                        exceeded_extremum = -1 if current_value < req_eff_table['Min'] else 1  # -1 is for Min, 1 for Max
                        mean_value = (req_eff_table['Min'] + req_eff_table['Max']) / 2
                        mean_property_after = self.get_dynamic_tool_property_after_operation(operation_node=operation_node,
                                                                                                tool_id=tool_id,
                                                                                                property_name=property_name,
                                                                                                start_value=mean_value)
                        effect_direction = -1 if mean_property_after < mean_value else 1
                        property_after_setup = 0.0
                        if exceeded_extremum*effect_direction == 1:
                            property_after_setup = req_eff_table[limit_name_dict[-exceeded_extremum]]
                        else:
                            property_after_setup = req_eff_table[limit_name_dict[exceeded_extremum]]
                        # Apply time, energy and costs for the dynamic property setup
                        # TODO: Setup energy and cost implementation - will require some additional production system variables
                        property_delta = property_after_setup - current_value
                        tool_obj : Tool = self.tools[tool_id]
                        if property_delta > 0.0:
                            total_setup_duration += tool_obj.dynamic_properties[property_name]['Time/unit+'] * property_delta  # seconds
                        else:
                            total_setup_duration += tool_obj.dynamic_properties[property_name]['Time/unit-'] * property_delta  # seconds
                        self.tool_state_tracker[tool_id][property_name] = property_after_setup

            if not all_tools_in_use or len(tools_needing_property_setup) > 0:
                print('    Tool setup is required.')
                if workstation.seized_worker != '':
                    print(f'    {workstation.seized_worker} is at the workstation to execute setup, setting their status to SETTING_UP.')
                    self.workers[workstation.seized_worker].status = WorkerStatus.SETTING_UP
                    self.workers[workstation.seized_worker].log_status_change(self.timestamp)
                    workstation.status.append(WorkstationStatus.SETUP)
                    print('    Added SETUP to workstation status list.')
                    workstation.log_status_change(self.timestamp)
                    self.event_queue.append(SetupFinishedEvent(timestamp=self.timestamp + total_setup_duration, workstation=workstation))

        # Generate pickup requests for blocking physical output buffers if needed
        if not product_fits_into_output:
            print('    Operation products will not fit into output buffers.')
            if WorkstationStatus.BLOCKED not in workstation.status and batch_complete:
                workstation.status.append(WorkstationStatus.BLOCKED)
                print('    Added BLOCKED to workstation status list.')
                workstation.log_status_change(self.timestamp)
        elif product_fits_into_output:
            print('    Operation products will fit into output buffers.')
            if WorkstationStatus.BLOCKED in workstation.status:
                workstation.status.remove(WorkstationStatus.BLOCKED)
                print('    Removed BLOCKED from workstation status list.')
                workstation.log_status_change(self.timestamp)
            
        # Execute the operation if all requirements are fulfilled
        if all([WorkstationStatus.WAITING_FOR_MATERIAL not in workstation.status,
               WorkstationStatus.WAITING_FOR_TOOLS not in workstation.status,
               WorkstationStatus.WAITING_FOR_WORKER not in workstation.status,
               WorkstationStatus.SETUP not in workstation.status,
               WorkstationStatus.BLOCKED not in workstation.status,
               batch_complete]):
            print('    All requirements for operation execution are fulfilled.')
            workstation.status = list()
            print('    Emptied workstation status list.')
            workstation.status.append(WorkstationStatus.BUSY)
            print('    Added BUSY to workstation status list.')
            workstation.log_status_change(self.timestamp, (operation_id, product_id, order_id, product_instance))
            if len(all_required_worker_capabilities) > 0:
                self.workers[workstation.seized_worker].status = WorkerStatus.BUSY
                print('    Set worker status to BUSY.')
                self.workers[workstation.seized_worker].log_status_change(self.timestamp)
            operation_progress[operation_id]['status'] = OperationStatus.PROCESSING
            print('    Set operation status to PROCESSING.')
            operation_progress[operation_id]['start_time'] = self.timestamp
            self.event_queue.appendleft(OperationFinishedEvent(timestamp=self.timestamp + operation_progress[operation_id]['remaining_work'],
                                                            workstation=workstation,
                                                            operation_id=(operation_id, product_id, order_id, product_instance)))
            operation_progress[operation_id]['finish_time'] = self.timestamp + operation_progress[operation_id]['remaining_work']
            # Transform required WIP components into an instance of the operation product
            for rc, rq in required_components.items():
                already_removed_qty = 0
                if already_removed_qty < rq:
                    for d in workstation.wip_components:
                        if d['Component'] == rc:
                            d['Quantity'] -= rq
                            already_removed_qty += rq
            workstation.wip_components.append({'Component': operation_node.output_name, 'Quantity': 1})
            print('    Transformed inputs into output.')

        print('    Exiting work on operation.')
        return True


    def apply_transport_routing_heuristic(self, source, eligible_transport, heuristic):
        '''
        Applies a transport routing heuristic and directly calls set_action(), bypassing get_legal_actions().
        Gets called from handle_transport_order() if TRANSPORT_ROUTING is configured to be handled by a heuristic.
        '''
        chosen_transport = ''

        # Vector of distances between transport machines and the source to enable CT
        distances_to_source = []
        # Vector of numbers of queued transport orders to enable LQTO
        queued_transport_orders = []

        for transport_id in eligible_transport:
            transport_machine : TransportMachine = self.transport_machines[transport_id]
            distance_to_source = math.inf
            try:
                if transport_machine.current_location != 'Shopfloor':
                    distance_to_source = self.get_distance(transport_machine.current_location, source)
                else:
                    # Take the transport machine's destination as the basis to decide how far it is
                    distance_to_source = self.get_distance(transport_machine.destination, source)
            except KeyError:
                # Unspecified distance
                pass
            distances_to_source.append(distance_to_source)

            queued_transport_orders.append(len(transport_machine.transport_order_list))
            
        if heuristic == 'Closest transport (CT)':
            chosen_transport = eligible_transport[numpy.argmin(distances_to_source)]

        if heuristic == 'Least queued transport orders (LQTO)':
            chosen_transport = eligible_transport[numpy.argmin(queued_transport_orders)]

        if heuristic == 'Random':
            chosen_transport = eligible_transport[numpy.random.choice(range(len(eligible_transport)))]

        i = self.action_matrix_row_dict[chosen_transport]
        j = self.action_matrix_col_dict[source]
        action_int = i * self.action_matrix_n_cols + j
        self.set_action(action_int)


    def apply_transport_sequencing_heuristic(self, transport_id, possible_targets, heuristic):
        '''
        Applies a transport sequencing heuristic and directly calls set_action(), bypassing get_legal_actions().
        Gets called from handle_transport_order() if TRANSPORT_SEQUENCING is configured to be handled by a heuristic.
        '''
        # The "skip" option is not supported by heuristics
        if 'skip' in possible_targets:
            possible_targets.remove('skip')
        possible_targets = list(possible_targets)  # in case a set object was provided

        chosen_target = ''

        # Vector of distances between transport machines and targets to enable CD
        distances_to_targets = []

        transport_machine : TransportMachine = self.transport_machines[transport_id]

        for target in possible_targets:
            distance_to_target = math.inf
            try:
                if transport_machine.current_location != 'Shopfloor':
                    distance_to_target = self.get_distance(transport_machine.current_location, target)
                else:
                    # Take the transport machine's destination as the basis to decide how far it is
                    distance_to_target = self.get_distance(transport_machine.destination, target)
            except KeyError:
                # Unspecified distance
                pass
            distances_to_targets.append(distance_to_target)

        if heuristic == 'Closest destination (CD)':
            chosen_target = possible_targets[numpy.argmin(distances_to_targets)]

        if heuristic == 'FIFO':
            chosen_target = possible_targets[0]

        if heuristic == 'Random':
            chosen_target = possible_targets[numpy.random.choice(range(len(possible_targets)))]

        i = self.action_matrix_row_dict[transport_id]
        j = self.action_matrix_col_dict[chosen_target]
        action_int = i * self.action_matrix_n_cols + j
        self.set_action(action_int)


    def handle_transport_order(self, component_dict, source, destination, eligible_transport, postponed=False):
        '''
        Returns True if the transport order needs a TRANSPORT_ROUTING or a TRANSPORT_SEQUENCING.
        Raises a RuntimeError if there are no eligible transport machines for the required transport task.
        '''
        if len(eligible_transport) == 0:
            print(f'There are no eligible transport machines for the transport order from {source} to {destination}!')
            raise RuntimeError
        
        if len(eligible_transport) == 1:
            # If there is only a single eligible TransportMachine, put this TransportOrder into its transport_order_list.
            transport_machine : TransportMachine = self.transport_machines[eligible_transport[0]]
            # The routing decision is trivial, don't handle it explicitly, just add transport order into the machine's order list
            for component, quantity in component_dict.items():
                transport_order_item = {
                    'Component': component,
                    'Quantity': quantity,
                    'Source': source,
                    'Destination': destination,
                    'Commitment': False,
                    'En route': False
                }
                transport_machine.transport_order_list.append(transport_order_item)

            # If the transport machine is currently en route or (un)loading, postpone the sequencing decision
            if any([TransportMachineStatus.MOVING_TO_SOURCE in transport_machine.status,
                   TransportMachineStatus.EXECUTING_TRANSPORT in transport_machine.status,
                   TransportMachineStatus.LOADING in transport_machine.status,
                   TransportMachineStatus.UNLOADING in transport_machine.status]):
                self.required_action_type = None
                self.event_queue.appendleft(TransportSequencingPostponed(timestamp=self.timestamp, transport_machine=transport_machine))
                return True
            
            # Make a list of all possible workstation and inventory IDs that the transport machine can head to
            possible_targets = [item['Source'] for item in transport_machine.transport_order_list]
            if not postponed:
                possible_targets.append('skip')  # In case the transport machine has to wait
            possible_targets = sorted(set(list(possible_targets)))

            self.required_action_type = ActionType.TRANSPORT_SEQUENCING
            self.action_relevant_info = (eligible_transport[0], possible_targets)

            # Apply a heuristic if so configured
            if self.action_config['Transport sequencing'][0] == False:  # indirect action
                self.apply_transport_sequencing_heuristic(transport_id=self.action_relevant_info[0],
                                                          possible_targets=self.action_relevant_info[1],
                                                          heuristic=self.action_config['Transport sequencing'][1])

            return True
        
        if len(eligible_transport) > 1:
            # If there are multiple eligible TransportMachines, a TRANSPORT_ROUTING decision/action is needed
            self.required_action_type = ActionType.TRANSPORT_ROUTING
            self.action_relevant_info = (component_dict, source, destination, eligible_transport)

            # Apply a heuristic if so configured
            if self.action_config['Transport routing'][0] == False:  # indirect action
                self.apply_transport_routing_heuristic(source=source,
                                                       eligible_transport=eligible_transport,
                                                       heuristic = self.action_config['Transport routing'][1])

            return True


    def execute_transport_order(self, material_source : str, transport_machine : TransportMachine):
        '''
        Gets called once the next target for the transport machine is chosen and returns True
        if the program can continue working on the event queue,
        i.e. all relevant resource requests and other events regarding this transport order have been created.
        '''
        # If the transport machine accepts manual worker capabilities, make sure that such a worker is present or requested;
        worker_capabilities_present, missing_capabilities = transport_machine.worker_capabilities_present(self)
        if not worker_capabilities_present:
            if TransportMachineStatus.WAITING_FOR_WORKER not in transport_machine.status:
                self.event_queue.append(WorkerCapabilitiesRequest(timestamp=self.timestamp,
                                                                capability_list=missing_capabilities,
                                                                target=transport_machine))
                transport_machine.status.append(TransportMachineStatus.WAITING_FOR_WORKER)
        elif worker_capabilities_present:
            if TransportMachineStatus.WAITING_FOR_WORKER in transport_machine.status:
                transport_machine.status.remove(TransportMachineStatus.WAITING_FOR_WORKER)

        # Source means materials source (where materials have to be taken from currently)
        # Destination means where the transport machine has to move to
        destination = None
        if material_source == "Shopfloor":
            # Case on simulation start
            material_source = transport_machine.departed_from  # preventively set in set_action() - TRANSPORT_SEQUENCING

        if material_source in self.workstations.keys():
            destination : Workstation = self.workstations[material_source]
        if material_source in self.inventories.keys():
            destination : Inventory = self.inventories[material_source]

        # Be at or go to the chosen "source" location where it will collect materials;
        if transport_machine.current_location != material_source:
            if all([TransportMachineStatus.WAITING_FOR_WORKER not in transport_machine.status,
                   TransportMachineStatus.UNLOADING not in transport_machine.status]):
                # Calculate movement time (int seconds) from current location to destination
                movement_time = 0
                if transport_machine.current_location == 'Shopfloor':
                    # Should only happen on simulation start, let's assume that transport is directly at the destination then
                    movement_time = 0
                    transport_machine.current_location = material_source
                else:
                    movement_time = math.ceil(self.get_distance(transport_machine.current_location, material_source) / transport_machine.speed_factor)
                self.event_queue.append(TransportArrivalEvent(timestamp=self.timestamp + movement_time,
                                                              transport_machine=transport_machine,
                                                              destination=destination))
                transport_machine.status.append(TransportMachineStatus.MOVING_TO_SOURCE)

        # If there are multiple rows in the transport machine's transport order list having the same "source",
        # pick materials according to the first occurence in the transport order list, aggregate same material;
        if all([transport_machine.current_location == material_source,
               TransportMachineStatus.WAITING_FOR_WORKER not in transport_machine.status,
               TransportMachineStatus.LOADING not in transport_machine.status,
               TransportMachineStatus.READY not in transport_machine.status]):
            # Transport machine is in no case moving to source here
            if TransportMachineStatus.MOVING_TO_SOURCE in transport_machine.status:
                transport_machine.status.remove(TransportMachineStatus.MOVING_TO_SOURCE)
            # Find the first occurence of any material that needs to be taken away from this source
            objects_to_remove = {'Component': '', 'Quantity': 0}
            first_component = ''
            first_target = ''
            for item in transport_machine.transport_order_list:
                if item['Source'] == material_source:
                    first_component = item['Component']
                    first_target = item['Destination']
                    break
            objects_to_remove['Component'] = first_component
            # Transport machine's batch size specification is the limit
            test_payload = deepcopy(transport_machine.payload)
            for item in transport_machine.transport_order_list:
                # Find only rows that have matching components, source and destination
                if all([item['Source'] == material_source,
                       item['Destination'] == first_target,
                       item['Component'] == first_component]):
                    # Check transport machine batch size specification
                    if transport_machine.accepts_objects(objects=(item['Component'], item['Quantity']),
                                                         wip_components=test_payload):
                        # Update batch size testing variable
                        test_payload.append({'Component': item['Component'], 'Quantity': item['Quantity']})
                        objects_to_remove['Quantity'] += item['Quantity']
                        item['Commitment'] = True
            # Check whether any of the examined components could be loaded
            if objects_to_remove['Quantity'] == 0:
                print(f'Warning: No {objects_to_remove['Component']} can be put into payload of {transport_machine.machine_id}!')
            # Move that amount of materials into the payload;
            transport_machine.payload.append(objects_to_remove)
            # Use the "No tool"-->"No tool" setup matrix entry (if there is any) to approximate loading time, generate a LoadingFinishedEvent (is it needed at all?);
            loading_duration = 0
            if len(transport_machine.setup_matrix) > 0:
                loading_duration = self.get_int_seconds(time_value=transport_machine.setup_matrix['No tool']['No tool'],
                                                        time_unit=transport_machine.hardware_setup_time_unit)
            transport_machine.status.append(TransportMachineStatus.LOADING)
            self.event_queue.append(LoadingFinishedEvent(timestamp=self.timestamp + loading_duration,
                                                         transport_machine=transport_machine,
                                                         location=destination,
                                                         objects=[objects_to_remove]))
            
        # Create a TransportArrivalEvent according to the global distance matrix and the transport machine's speed;
        if all([transport_machine.current_location == material_source,
               TransportMachineStatus.WAITING_FOR_WORKER not in transport_machine.status,
               TransportMachineStatus.READY in transport_machine.status]):
            transport_machine.status.remove(TransportMachineStatus.READY)
            transport_machine.status.append(TransportMachineStatus.EXECUTING_TRANSPORT)
            transport_machine.departed_from = material_source
            # Get target name from transport_order_list with Commitment=True, set En route=True for executed transport order(s)
            target = ''
            for item in transport_machine.transport_order_list:
                if item['Commitment'] == True:
                    target = item['Destination']
                    item['En route'] = True
            transport_duration = math.ceil(self.get_distance(material_source, target) / transport_machine.speed_factor)
            destination = ''  # The destination changes from the material source to the "consuming" workstation or inventory
            if target in self.workstations.keys():
                destination : Workstation = self.workstations[target]
            if target in self.inventories.keys():
                destination : Inventory = self.inventories[target]
            transport_machine.destination = target
            self.event_queue.append(TransportArrivalEvent(timestamp=self.timestamp + transport_duration,
                                                          transport_machine=transport_machine,
                                                          destination=destination))
            
        # Once arrived at the transport order destination, do the unloading.
        # UnloadingFinishedEvent in the main loop will lead to a MaterialsArrivalEvent.
        if TransportMachineStatus.UNLOADING in transport_machine.status:
            # Prepare a list of component-quantity dictionaries to take_objects_into_physical_input_buffers()
            objects_to_remove = {'Component': '', 'Quantity': 0}
            first_component = ''
            for item in transport_machine.transport_order_list:
                if all([item['Destination'] == transport_machine.current_location,
                        item['Commitment'] == True,
                        item['En route'] == True]):
                    first_component = item['Component']
                    break
            objects_to_remove['Component'] = first_component
            for item in transport_machine.transport_order_list:
                if all([item['Destination'] == transport_machine.current_location,
                        item['Commitment'] == True,
                        item['En route'] == True,
                        item['Component'] == first_component]):
                    objects_to_remove['Quantity'] += item['Quantity']

            # If the destination buffer is full (i.e. workstation can't take delivered objects),
            # append IDLE status. This status can serve as a flag that once some operation at this
            # workstation has started, it's smart to retry unloading this transport machine again.
            curr_loc = transport_machine.current_location
            curr_loc_obj = None

            # Attention: actual moving of materials from a transport machine into input buffers or inventories
            # happens while handling MaterialsArrivalEvents (after UnloadingFinishedEvent) in run_until_decision_point().
            # Here the algorithm only test whether unloading should be done at all.
            if curr_loc in self.workstations.keys():
                curr_loc_obj : Workstation = deepcopy(self.workstations[curr_loc])
            if curr_loc in self.inventories.keys():
                curr_loc_obj : Inventory = deepcopy(self.inventories[curr_loc])

            if isinstance(curr_loc_obj, Workstation):
                if not curr_loc_obj.take_objects_into_physical_input_buffers([objects_to_remove]):
                    if not TransportMachineStatus.IDLE in transport_machine.status:
                        transport_machine.status.append(TransportMachineStatus.IDLE)
                    return True
            if isinstance(curr_loc_obj, Inventory):
                if not curr_loc_obj.take_objects([objects_to_remove]):
                    if not TransportMachineStatus.IDLE in transport_machine.status:
                        transport_machine.status.append(TransportMachineStatus.IDLE)
                    return True

            # Use the "No tool"-->"No tool" setup matrix entry (if there is any) to approximate unloading time, generate an UnloadingFinishedEvent (is it needed at all?);
            unloading_duration = 0
            if len(transport_machine.setup_matrix) > 0:
                unloading_duration = self.get_int_seconds(time_value=transport_machine.setup_matrix['No tool']['No tool'],
                                                        time_unit=transport_machine.hardware_setup_time_unit)
            self.event_queue.append(UnloadingFinishedEvent(timestamp=self.timestamp + unloading_duration,
                                                         transport_machine=transport_machine,
                                                         location=transport_machine.current_location,
                                                         objects=[objects_to_remove]))
            
            if TransportMachineStatus.IDLE in transport_machine.status:
                transport_machine.status.remove(TransportMachineStatus.IDLE)
            
        return True


    def get_legal_actions(self):
        '''Returns an integer list of all legal actions for the current state of the production system depending on the currently required action type.
        '''

        legal_actions = []

        # Empty the action matrix from any previous manipulations
        self.action_matrix = numpy.zeros((self.action_matrix_n_rows, self.action_matrix_n_cols), dtype="int32")

        if self.required_action_type is None:
            # In the very beginning of the simulation we first need to hit an event to even start deciding on anything. For this, dummy action -1 is used.
            legal_actions = [-1]

        if self.required_action_type == ActionType.WORKSTATION_ROUTING:
            operation = self.action_relevant_info[0]
            operation_id = operation[0]
            product_id = operation[1]
            order_id = operation[2]
            eligible_workstation_ids = self.action_relevant_info[1]
            # Release time sanity check
            if self.order_progress[order_id]['release_time'] > self.timestamp:
                print(f'The order {order_id} has not been released to the planning algorithm yet. The simulation logic should not be requesting an action.')
                raise RuntimeError
            if len(eligible_workstation_ids) == 0:
                print(f'There are no eligible workstations for {operation_id} of {product_id}. Something is wrong with the simulation logic.')
                raise RuntimeError
            elif len(eligible_workstation_ids) == 1:
                print(f'There is only one eligible workstation for {operation_id} of {product_id} but a workstation routing decision was requested. Something is wrong with the simulation logic.')
                raise RuntimeError
            elif len(eligible_workstation_ids) > 1:
                i = self.action_matrix_row_dict[operation_id + '|' + product_id + '|' + order_id]
                for ews in eligible_workstation_ids:
                    j = self.action_matrix_col_dict[ews]
                    self.action_matrix[i][j] = 1
            
        if self.required_action_type == ActionType.WORKSTATION_SEQUENCING:
            workstation_id = self.action_relevant_info[0]
            operations = self.action_relevant_info[1]  # list of tuples
            if len(operations) == 0:
                print(f'The workstation {workstation_id} has no operations to choose from. Something is wrong with the simulation logic.')
                raise RuntimeError
            else:
                j = self.action_matrix_col_dict[workstation_id]
                for op in operations:
                    if op[0] != 'skip':
                        row = op[0] + '|' + op[1] + '|' + op[2]
                    else:
                        row = 'skip'
                    i = self.action_matrix_row_dict[row]
                    self.action_matrix[i][j] = 1

        if self.required_action_type == ActionType.TRANSPORT_SEQUENCING:
            transport_id = self.action_relevant_info[0]
            target_ids = self.action_relevant_info[1]  # list of str, 'skip' possible
            if len(target_ids) == 0:
                print(f'The transport machine {transport_id} has no destinations to choose from. Something is wrong with the simulation logic.')
                raise RuntimeError
            else:
                i = self.action_matrix_row_dict[transport_id]
                for target in target_ids:
                    j = self.action_matrix_col_dict[target]
                    self.action_matrix[i][j] = 1

        if self.required_action_type == ActionType.TRANSPORT_ROUTING:
            source_id = self.action_relevant_info[1]
            transport_ids = self.action_relevant_info[3]  # list of str
            if len(transport_ids) == 0:
                print(f'The source {source_id} has no transport machines to choose from. Something is wrong with the simulation logic.')
                raise RuntimeError
            else:
                j = self.action_matrix_col_dict[source_id]
                for tm in transport_ids:
                    i = self.action_matrix_row_dict[tm]
                    self.action_matrix[i][j] = 1


        # Direct legal actions ("full picture")
        for i in range(self.action_matrix_n_rows):
            for j in range(self.action_matrix_n_cols):
                if self.action_matrix[i][j] == 1:
                    legal_actions.append(i * self.action_matrix_n_cols + j)

        # TODO: Indirect legal actions (heuristics) - just a different set of rules to deal with the same "full picture"

        return legal_actions


    def set_action(self, action):
        '''Applies the provided integer action to the production system and updates it until the next action is needed.
        '''
        print(f'\n--> Setting action {action}')

        if action == -1:
            return self.run_until_decision_point()
        
        j = action % self.action_matrix_n_cols
        i = int((action - j) / self.action_matrix_n_cols)

        if self.required_action_type == ActionType.WORKSTATION_SEQUENCING:
            # Erase all ones in the j-th column from the legal action matrix because only one operation is chosen 
            for row in range(self.action_matrix_n_rows):
                self.action_matrix[row][j] = 0

            operation_info_str = self.action_matrix_reverse_row_dict[i]
            print('WORKSTATION_SEQUENCING action:')
            print(f'    operation to process next: {operation_info_str}')
            operation_info_str_chunks = operation_info_str.split('|')
            operation_id = operation_info_str_chunks[0]

            location_info_str = self.action_matrix_reverse_col_dict[j]
            print(f'    at workstation: {location_info_str}')
                
            ws : Workstation = self.workstations[location_info_str]

            print(f'    current input operation buffer: {str(ws.input_operation_buffer)}')
            print(f'    current WIP operations: {str(ws.wip_operations)}')
            print(f'    current physical input buffer contents: {str([b.contents for b in ws.physical_input_buffers.values()])}')
            print(f'    current physical WIP components: {str(ws.wip_components)}')

            if operation_id == 'skip':
                # Not committing to any assigned operation is treated as a signal that tools and workers
                # can be now seized by other workstations that need them.
                # Tools currently in use are moved back to their tool pools of origin.
                # That may enable a ToolsRequest to be fulfilled.
                self.handle_workstation_sequencing_skip(workstation=ws)
                self.event_queue.appendleft(WorkstationSequencingPostponed(timestamp=self.timestamp, workstation=self.workstations[location_info_str]))
                self.required_action_type = None 
                return True
            
            product_id = operation_info_str_chunks[1]
            order_id = operation_info_str_chunks[2]

            # See if this workstation has a machine that does only batch processing,
            # because it requires special handling of sequencing decisions.
            ws_is_batch_processing = False
            if ws.machine != '' and self.stationary_machines[ws.machine].batch_processing:
                ws_is_batch_processing = True

            if not ws_is_batch_processing:
                # Find the first instance of this operation-product-order in operation input buffer
                instance = None
                for rho in ws.input_operation_buffer:
                    if all([rho[0] == operation_id,
                        rho[1] == product_id,
                        rho[2] == order_id]):
                        instance = rho[3]
                        break
                # Remove the first instance matching the selected operation from the input operation buffer
                ws.input_operation_buffer.remove((operation_id, product_id, order_id, instance))
                # Move the selected operation into workstation's wip_operations
                ws.wip_operations.append((operation_id, product_id, order_id, instance))
                # Set location and status of the operation
                product_progress = self.order_progress[order_id]['product_progress']
                for instance_data in product_progress:
                    if instance_data['product_id'] == product_id and instance_data['product_instance'] == instance:
                        instance_data['operation_progress'][operation_id]['location'] = location_info_str
                        instance_data['operation_progress'][operation_id]['status'] = OperationStatus.COMMITTED
                        # Generate requests for any resources that are missing or continue till OperationFinishedEvent is created
                        self.required_action_type = None
                        return self.work_on_operation(operation_id, product_id, order_id, instance, instance_data['operation_progress'], ws)
            
            elif ws_is_batch_processing:
                # Find all instances of this operation-product-order in operation input buffer
                instances = []
                for rho in ws.input_operation_buffer:
                    if all([rho[0] == operation_id,
                        rho[1] == product_id,
                        rho[2] == order_id]):
                        instances.append(rho[3])
                # Collect the maximum number of operations that will fit in the batch (if not enough of them assigned - WorkstationSequencingPostponed?)
                # Find the maximum number of instances to be taken into O-WIP which still can accepted by the machine's wip_components
                max_num_inst = 0
                machine_obj : Machine = self.stationary_machines[ws.machine]
                operation_node = None
                for op in self.product_operations[product_id]:
                    if op.operation_name == operation_id:
                        operation_node = op
                        break
                # Assumption: every operation in a batch machine takes only one type of components (i.e. there are no batch assembly operations)
                assert len(operation_node.components.keys()) == 1
                first_key = next(iter(operation_node.components))
                first_val = operation_node.components[first_key]
                for c in range(len(instances)):
                    objects = (first_key, first_val * (c + 1))
                    # Instead of checking whether the machine accepts objects (until the materials arrive, physical WIP is empty anyway)
                    # check whether committing to yet another operation is still possible
                    #if machine_obj.accepts_objects(objects=objects, wip_components=ws.wip_components):
                    potential_phys_wip_single = []
                    for committed_op in ws.wip_operations:
                        o_node = self.find_operation_by_name(operation_name=committed_op[0], operation_list=self.product_operations[committed_op[1]])
                        fk = next(iter(o_node.components))
                        fv = o_node.components[fk]
                        potential_phys_wip_single.append({'Component': fk, 'Quantity': fv})
                    # Aggregate by component name
                    potential_phys_wip_aggreg = []
                    for single_cqd in potential_phys_wip_single:
                        if single_cqd['Component'] in [potential_phys_wip_aggreg[p]['Component'] for p in range(len(potential_phys_wip_aggreg))]:
                            for agg_cqd in potential_phys_wip_aggreg:
                                if agg_cqd['Component'] == single_cqd['Component']:
                                    agg_cqd['Quantity'] += 1
                        else:
                            potential_phys_wip_aggreg.append(single_cqd)
                    if machine_obj.accepts_objects(objects=objects, wip_components=potential_phys_wip_aggreg):
                        max_num_inst = c + 1  # += 1
                if max_num_inst == 0:
                    self.event_queue.appendleft(WorkstationSequencingPostponed(timestamp=self.timestamp, workstation=self.workstations[location_info_str]))
                    self.required_action_type = None
                    return True
                else:
                    committed_all_batch_ops = []  # list of booleans
                    for k in range(max_num_inst):
                        instance_idx = instances[k]
                        # Remove the first instance matching the selected operation from the input operation buffer
                        ws.input_operation_buffer.remove((operation_id, product_id, order_id, instance_idx))
                        # Move the selected operation into workstation's wip_operations
                        ws.wip_operations.append((operation_id, product_id, order_id, instance_idx))
                        # Set location and status of the operation
                        product_progress = self.order_progress[order_id]['product_progress']
                        # Prepare batch_complete argument for the work_on_operation() function
                        batch_complete = True
                        if max_num_inst > 1:
                            # This flag is only relevant when multiple operations need to be collected
                            if k < max_num_inst - 1:
                                batch_complete = False
                            if k == max_num_inst - 1:
                                batch_complete = True
                            
                        for instance_data in product_progress:
                            if instance_data['product_id'] == product_id and instance_data['product_instance'] == instance_idx:
                                instance_data['operation_progress'][operation_id]['location'] = location_info_str
                                instance_data['operation_progress'][operation_id]['status'] = OperationStatus.COMMITTED
                                # Generate requests for any resources that are missing or continue till OperationFinishedEvent is created
                                self.required_action_type = None
                                committed_all_batch_ops.append(self.work_on_operation(operation_id,
                                                                                      product_id,
                                                                                      order_id,
                                                                                      instance_idx,
                                                                                      instance_data['operation_progress'],
                                                                                      ws,
                                                                                      batch_complete))
                    return all(committed_all_batch_ops)

        if self.required_action_type == ActionType.WORKSTATION_ROUTING:
            # Erase all ones in the i-th row of the action matrix because only one workstation gets chosen
            for col in range(self.action_matrix_n_cols):
                self.action_matrix[i][col] = 0

            operation_info_str = self.action_matrix_reverse_row_dict[i]
            print('WORKSTATION_ROUTING action:')
            print(f'    assigned operation: {operation_info_str}')
            operation_info_str_chunks = operation_info_str.split('|')
            operation_id = operation_info_str_chunks[0]
            product_id = operation_info_str_chunks[1]
            order_id = operation_info_str_chunks[2]
            # Just to check that the RL agent's decision also matches what push_operation_downstream() allows: 
            assert operation_id == self.action_relevant_info[0][0]
            assert product_id == self.action_relevant_info[0][1]
            assert order_id == self.action_relevant_info[0][2]

            location_info_str = self.action_matrix_reverse_col_dict[j]
            print(f'    to workstation: {location_info_str}')

            ws : Workstation = self.workstations[location_info_str]

            print(f'    current input operation buffer: {str(ws.input_operation_buffer)}')
            print(f'    current WIP operations: {str(ws.wip_operations)}')
            print(f'    current physical input buffer contents: {str([b.contents for b in ws.physical_input_buffers.values()])}')
            print(f'    current physical WIP components: {str(ws.wip_components)}')

            # Put the operation into the input operation buffer of the selected workstation
            product_instance = self.action_relevant_info[0][3]
            #ws.input_operation_buffer.append((operation_id, product_id, order_id, product_instance)) --> happens in push_operation_downstream
            # Set location and status of the operation
            product_progress = self.order_progress[order_id]['product_progress']
            for instance_data in product_progress:
                if instance_data['product_id'] == product_id and instance_data['product_instance'] == product_instance:
                    instance_data['operation_progress'][operation_id]['location'] = location_info_str
                    instance_data['operation_progress'][operation_id]['status'] = OperationStatus.ASSIGNED
                    # Generate MaterialsRequest
                    #component_dict = self.find_operation_by_name(operation_name=operation_id, operation_list=self.product_operations[product_id]).components
                    #self.event_queue.append(MaterialsRequest(timestamp=self.timestamp, component_dict=component_dict, target_workstation=ws))
                    # Try sequencing on the workstation that just received the operation
                    # TODO: check whether erasing required action type here is necessary
                    self.required_action_type = None 
                    return self.push_operation_downstream(operation_id, product_id, order_id, product_instance, [location_info_str], instance_data['operation_progress'])

        if self.required_action_type == ActionType.TRANSPORT_ROUTING:
            # Erase all ones in the j-th column from the legal action matrix because only one transport machine is chosen 
            for row in range(self.action_matrix_n_rows):
                self.action_matrix[row][j] = 0

            transport_id = self.action_matrix_reverse_row_dict[i]
            location_info_str = self.action_matrix_reverse_col_dict[j]
            print('TRANSPORT_ROUTING action:')
            print(f'    selected transport machine: {transport_id}')
            print(f'    to collect components at: {location_info_str}')

            transport_machine : TransportMachine = self.transport_machines[transport_id]
            print('    --- Transport machine info ---')
            print(f'    current payload: {str(transport_machine.payload)}')

            print('    --- Material source info ---')
            if location_info_str in self.workstations.keys():
                ws : Workstation = self.workstations[location_info_str]
                #print(f'    current input operation buffer: {str(ws.input_operation_buffer)}')
                #print(f'    current WIP operations: {str(ws.wip_operations)}')
                print(f'    current physical output buffer contents: {str([b.contents for b in ws.physical_output_buffers.values()])}')
                print(f'    current physical WIP components: {str(ws.wip_components)}')
            if location_info_str in self.inventories.keys():
                inv : Inventory = self.inventories[location_info_str]
                print(f'    current contents: {str(inv.contents)}')

            component_dict = self.action_relevant_info[0]
            source = self.action_relevant_info[1]
            destination = self.action_relevant_info[2]

            return self.handle_transport_order(component_dict, source, destination, [transport_id])

        if self.required_action_type == ActionType.TRANSPORT_SEQUENCING:
            # Erase all ones in the i-th row of the action matrix because only one destination (workstation or inventory) gets chosen
            for col in range(self.action_matrix_n_cols):
                self.action_matrix[i][col] = 0

            transport_id = self.action_relevant_info[0]
            location_info_str = self.action_matrix_reverse_col_dict[j]
            print('TRANSPORT_SEQUENCING action:')
            print(f'    sent transport machine: {transport_id}')
            print(f'    to: {location_info_str}')

            transport_machine : TransportMachine = self.transport_machines[transport_id]
            print('    --- Transport machine info ---')
            print(f'    current payload: {str(transport_machine.payload)}')

            if location_info_str == 'skip':
                self.event_queue.appendleft(TransportSequencingPostponed(timestamp=self.timestamp, transport_machine=transport_machine))
                self.required_action_type = None
                return True
            
            print('    --- Destination info ---')
            if location_info_str in self.workstations.keys():
                ws : Workstation = self.workstations[location_info_str]
                #print(f'    current input operation buffer: {str(ws.input_operation_buffer)}')
                #print(f'    current WIP operations: {str(ws.wip_operations)}')
                print(f'    current physical output buffer contents: {str([b.contents for b in ws.physical_output_buffers.values()])}')
                print(f'    current physical WIP components: {str(ws.wip_components)}')
            if location_info_str in self.inventories.keys():
                inv : Inventory = self.inventories[location_info_str]
                print(f'    current contents: {str(inv.contents)}')
                
            self.required_action_type = None

            # On simulation start, use transport machine's "departed_from" argument to replace "Shopfloor" by actual target
            if transport_machine.departed_from is None:
                transport_machine.departed_from = location_info_str

            # Make sure the transport order gets executed
            return self.execute_transport_order(material_source=location_info_str, transport_machine=self.transport_machines[transport_id])
   
        # Action types handled, erase variable
        self.required_action_type = None 


    def run_until_decision_point(self):
        '''
        Runs the production system according to its logic until a decision point for a control algorithm is reached.
        Returns True once a decision point is reached.
        '''
        # Follows the flowchart after cold/warm start handling.
        print('Entering the main simulation logic loop (running until decision)')

        while True:

            if len(self.event_queue) == 0:
                # Generate Events for any running operations or activities at simulation start
                # Generate all OrderReleaseEvents
                print('\nThe event queue is empty')

                for order_id, order_data in self.order_progress.items():
                    if order_data['release_time'] <= self.timestamp:
                        for instance_data in order_data['product_progress']:
                            for operation_id, operation_data in instance_data['operation_progress'].items():
                                if operation_data['status'] == OperationStatus.PROCESSING:
                                    self.event_queue.appendleft(OperationFinishedEvent(timestamp=self.timestamp + operation_data['remaining_work'],
                                                                                workstation=operation_data['location'],
                                                                                operation_id=operation_id))
                                    
                for workstation_id, workstation in self.workstations.items():
                    if WorkstationStatus.SETUP in workstation.status:
                        self.event_queue.append(SetupFinishedEvent(timestamp=self.timestamp + workstation.remaining_setup_time,
                                                                   workstation=workstation))
                    if WorkstationStatus.MAINTENANCE in workstation.status:
                        self.event_queue.append(MaintenanceFinishedEvent(timestamp=self.timestamp + workstation.remaining_maintenance_time, 
                                                                         workstation=workstation))
                    if WorkstationStatus.REPAIR in workstation.status:
                        self.event_queue.append(RepairFinishedEvent(timestamp=self.timestamp + workstation.remaining_repair_time,
                                                                    workstation=workstation))
                    
                for worker_id, worker in self.workers.items():
                    if worker.status == WorkerStatus.WALKING:
                        if worker.destination in self.workstations.keys():
                            self.event_queue.append(WorkerStationArrivalEvent(timestamp=self.timestamp + math.ceil(worker.distance_to_destination / self.walking_speed),
                                                                              workstation=self.workstations[worker.destination],
                                                                              worker=worker))
                        if worker.destination in self.transport_machines.keys():
                            self.event_queue.append(WorkerTransportArrivalEvent(timestamp=self.timestamp + math.ceil(worker.distance_to_destination / self.walking_speed),
                                                                              transport_machine=self.transport_machines[worker.destination],
                                                                              worker=worker))
                
                for transport_id, transport_machine in self.transport_machines.items():
                    if TransportMachineStatus.EXECUTING_TRANSPORT in transport_machine.status or TransportMachineStatus.MOVING_TO_SOURCE in transport_machine.status:
                        destination = None
                        if transport_machine.destination in self.workstations.keys():
                            destination = self.workstations[transport_machine.destination]
                        elif transport_machine.destination in self.inventories.keys():
                            destination = self.inventories[transport_machine.destination]
                        # TODO: When is a Buffer a destination? When it's attached to a Conveyor?
                        self.event_queue.append(TransportArrivalEvent(timestamp=self.timestamp + math.ceil(transport_machine.remaining_distance / transport_machine.speed_factor),
                                                                      transport_machine=transport_machine,
                                                                      destination=destination))
                    if TransportMachineStatus.LOADING in transport_machine.status:
                        location = None
                        if transport_machine.current_location in self.workstations.keys():
                            location = self.workstations[transport_machine.location]
                        elif transport_machine.current_location in self.inventories.keys():
                            location = self.inventories[transport_machine.location]
                        self.event_queue.append(LoadingFinishedEvent(timestamp=self.timestamp + transport_machine.remaining_handling_time,
                                                                     transport_machine=transport_machine,
                                                                     location=location))
                    if TransportMachineStatus.UNLOADING in transport_machine.status:
                        location = None
                        if transport_machine.current_location in self.workstations.keys():
                            location = self.workstations[transport_machine.location]
                        elif transport_machine.current_location in self.inventories.keys():
                            location = self.inventories[transport_machine.location]
                        self.event_queue.append(UnloadingFinishedEvent(timestamp=self.timestamp + transport_machine.remaining_handling_time,
                                                                     transport_machine=transport_machine,
                                                                     location=location))
                        
                # Generate all OrderReleaseEvents
                for order_id, order_data in self.order_progress.items():
                    self.event_queue.append(OrderReleaseEvent(timestamp=order_data['release_time'],
                                                              order=self.order_list.order_list[order_id]))

            if len(self.event_queue) > 0:
                print(f'\nThe event queue currently has {len(self.event_queue)} events')
                
                # Find the earliest timestamp of all events in the event queue
                earliest_timestamp = math.inf
                for event in self.event_queue:

                    # Exceptions: Events that stay "in the past" and aren't used to find the earliest timestamp.
                    # They remain in the event queue until handled.

                    # TODO: Check whether this messes up the timers update of workstations (KPI purposes)

                    if any([isinstance(event, WorkstationSequencingPostponed),
                            isinstance(event, PickupRequest),
                            isinstance(event, TransportSequencingPostponed)]):
                        continue

                    if isinstance(event, ToolsRequest):
                        # If a ToolsRequest has just been created or some of therein requested tools got released,
                        # such ToolsRequest will get checked again
                        if not event.just_created and not event.some_unavailable_tool_released:
                            continue

                    if isinstance(event, WorkerCapabilitiesRequest):
                        if not event.just_created and not event.some_worker_released:
                            continue

                    if isinstance(event, RawMaterialArrivalEvent):
                        # Raw material inventory overflows are waiting to be triggered by LoadingFinishedEvents
                        # or when components are moved from physical input buffer into wip_components of a workstation.
                        if event.rmi_overflow:
                            continue

                    if isinstance(event, MaterialsArrivalEvent):
                        if event.buffer_overflow:
                            continue

                    if event.timestamp <= earliest_timestamp:
                        earliest_timestamp = event.timestamp

                if earliest_timestamp >= self.end_timestamp:
                    # Simulation end time reached
                    self.timestamp = self.end_timestamp
                    break
                else:
                    # Simulation end time not reached yet
                    # Calculate time delta to call update_timers() of objects
                    delta_t = earliest_timestamp - self.timestamp
                    if delta_t > 0:
                        for ws in self.workstations.values():
                            ws.update_timers(delta_t)
                            ws.log_utilization_change(earliest_timestamp, earliest_timestamp - self.start_timestamp)
                        for wrkr in self.workers.values():
                            wrkr.update_timers(delta_t)

                # Pick the first event at the earliest timestamp
                earliest_event = None
                for event in self.event_queue:
                    if event.timestamp == earliest_timestamp:

                        if any([isinstance(event, WorkstationSequencingPostponed),
                                isinstance(event, PickupRequest),
                                isinstance(event, TransportSequencingPostponed)]):
                            continue

                        if isinstance(event, ToolsRequest):
                            # If a ToolsRequest has just been created or some of therein requested tools got released,
                            # such ToolsRequest will get checked again
                            if not event.just_created and not event.some_unavailable_tool_released:
                                continue

                        if isinstance(event, WorkerCapabilitiesRequest):
                            if not event.just_created and not event.some_worker_released:
                                continue

                        if isinstance(event, RawMaterialArrivalEvent):
                            # Raw material inventory overflows are waiting to be triggered by LoadingFinishedEvents
                            # or when components are moved from physical input buffer into wip_components of a workstation.
                            if event.rmi_overflow:
                                continue

                        if isinstance(event, MaterialsArrivalEvent):
                            if event.buffer_overflow:
                                continue

                        # Set the event that will be handled next
                        earliest_event = event
                        # Simulation time jumps to the timestamp of this earliest event
                        self.timestamp = event.timestamp
                        # Coinciding events are dealt with in FIFO order
                        break

                readable_date = datetime.fromtimestamp(earliest_event.timestamp).strftime(f'%d.%m.%Y %H:%M:%S')
                print(f'\n§§§ Handling {type(earliest_event).__name__} @ {readable_date} §§§')
                
                ##################################
                ### Handle all kinds of events ###
                ##################################

                if isinstance(earliest_event, OrderReleaseEvent):
                    # All initial operations of all product instances need to be routed to workstations
                    order_id = earliest_event.order.order_id
                    print(f'\nHandling OrderReleaseEvent for order {order_id}')
                    product_progress = self.order_progress[order_id]['product_progress']
                    all_initial_ops_routed = True
                    for instance_data in product_progress:
                        # Operations without precedence constraints (initial operations) or with all predecessors done
                        # can be routed to workstations' IOB. Operations are not routed to inventories since
                        # inventories are just storages for materials which are to be requested via a MaterialsRequest.
                        product_id = instance_data['product_id']
                        product_instance = instance_data['product_instance']
                        operation_progress = instance_data['operation_progress']
                        for operation_id in operation_progress.keys():
                            operation = self.find_operation_by_name(operation_id, self.product_operations[product_id])
                            # Check whether it is an initial operation (without any predecessors), find all eligible workstations.
                            if (operation_progress[operation_id]['status'] == OperationStatus.IN_BACKLOG and
                                len(operation_progress[operation_id]['predecessors']) == 0):
                                eligible_workstations = self.eligible_workstations_for_operation(operation)
                                all_initial_ops_routed = False
                                return self.push_operation_downstream(operation_id=operation_id,
                                                                      product_id=product_id,
                                                                      order_id=order_id,
                                                                      product_instance=product_instance,
                                                                      eligible_workstations=eligible_workstations,
                                                                      operation_progress=operation_progress)
                    # Delete the OrderReleaseEvent only once all of its initial operations are introduced into the system
                    if all_initial_ops_routed:
                        print(f'All initial operations in order {order_id} has been routed, removing OrderReleaseEvent')
                        self.event_queue.remove(earliest_event)

                elif isinstance(earliest_event, OperationFinishedEvent):
                    finished_op = earliest_event.operation_id
                    workstation : Workstation = earliest_event.workstation
                    print(f'\nHandling OperationFinishedEvent of operation {str(finished_op)} at workstation {workstation.workstation_id}')
                    #print(f'    Handling this event will{' ' if earliest_event.trigger_push_operation_downstream else ' not necessarily '}trigger further routing and sequencing actions.')

                    # Handle simultaneously finished operations at the same workstation (e.g. in a batch processing machine)
                    #operation_product_quantity = 1
                    if finished_op not in workstation.wip_operations:
                        print('    This operation is not in the operation WIP of the workstation anymore.')
                        self.required_action_type = None
                        self.event_queue.remove(earliest_event)

                        if WorkstationStatus.BUSY in workstation.status:
                            # TODO: This seems to be the right approach for finished batch operations
                            workstation.status.remove(WorkstationStatus.BUSY)
                            print('    Removed BUSY from the workstation status list.')
                            workstation.log_status_change(self.timestamp)
                        
                        # Retrigger postponed workstation sequencing
                        for wsp_event in self.event_queue:
                            if isinstance(wsp_event, WorkstationSequencingPostponed):
                                if wsp_event.workstation is None:
                                    # Such WorkstationSequencingPostponed will be removed
                                    # in the end of the main loop (cleaning). Ignore it here.
                                    continue
                                if wsp_event.workstation.workstation_id == workstation.workstation_id:
                                    print(f'\n... Handling WorkstationSequencingPostponed at {wsp_event.workstation.workstation_id}')
                                    
                                    # As a flag that this WorkstationSequencingPostponed can be deleted:
                                    wsp_event.workstation = None

                                    return self.push_operation_downstream(operation_id=None,
                                                                product_id=None,
                                                                order_id=None,
                                                                product_instance=None,
                                                                eligible_workstations=[workstation.workstation_id],
                                                                operation_progress=None,
                                                                postponed=True)

                        return True

                    _operation_products = list()  # List of Component-Quantity dictionaries for each product of (batched) operation(s)
                    _bundled_op_prods = list()  # Bundle outputs, e.g. if 5x C1.A were produced, the list will contain {'Component': 'C1.A'; 'Quantity': 5}
                    _finished_ops = list()  # List of quadruple operation symbols that are simultaneously finished at this workstation

                    #_batch_instance_list = [_instance]
                    #if len(workstation.wip_operations) > 1:
                    for o in workstation.wip_operations:

                        # Find the product of the finished operation
                        o_node = self.find_operation_by_name(o[0], self.product_operations[o[1]])
                        o_prod = o_node.output_name
                        # Populate per-operation output list
                        _operation_products.append({'Component': o_prod,
                                                    'Quantity': 1})
                        # Populate bundled output list
                        if o_prod in [_bundled_op_prods[b]['Component'] for b in range(len(_bundled_op_prods))]:
                            for comp_qty_dict in _bundled_op_prods:
                                if comp_qty_dict['Component'] == o_prod:
                                    comp_qty_dict['Quantity'] += 1
                        else:
                            _bundled_op_prods.append({'Component': o_prod, 'Quantity': 1})
                        # Populate list of simultaneously finished operations quadruple symbols
                        _finished_ops.append(o)

                    clone_workstation_1 = deepcopy(workstation)
                    clone_workstation_2 = deepcopy(workstation)

                    obj_single_move_results = [clone_workstation_1.move_objects_to_physical_output_buffer(objects_to_move=[_op_prod], production_system=self) for _op_prod in _operation_products]

                    # Need to bundle same components in case of quantity steps >1 in the physical output buffer
                    obj_bundle_move_results = [clone_workstation_2.move_objects_to_physical_output_buffer(objects_to_move=[_op_prod], production_system=self) for _op_prod in _bundled_op_prods]

                    # Rewrite products_moved_to_output (first entry) of obj_single_move_results to iterate over it later
                    for bmr in obj_bundle_move_results:

                        if bmr[0] == True:
                            _comp = bmr[2][0]['Component']
                            _qty = bmr[2][0]['Quantity']
                            # This bundle has been moved to output successfully
                            workstation.move_objects_to_physical_output_buffer(bmr[2], self)
                            _rewrite_counter = _qty
                            for s, smr in enumerate(obj_single_move_results):
                                if smr[2][0]['Component'] == _comp and _rewrite_counter > 0:
                                    obj_single_move_results[s] = (True, bmr[1], [{'Component': _comp, 'Quantity': 1}])
                                    # third element was smr[2], but it should be 1 since we are writing output results for single instances of components
                                    _rewrite_counter -= 1
                        else:
                            # A part of batch output couldn't be moved to the physical output buffer
                            # although there is a simulataneous OperationFinishedEvent here.
                            # This shouldn't happen since the operations should only start if the
                            # workstation is not blocked (physical output buffer has enough capacity).
                            raise NotImplementedError()

                    for smr in obj_single_move_results:

                        products_moved_to_output = smr[0]
                        output_idx1 = smr[1]
                        moved_objects = smr[2]

                        if products_moved_to_output:
                            # Do the actual moving of products, not testing on "cloned" workstations like above anymore.
                            #workstation.move_objects_to_physical_output_buffer(objects_to_move=moved_objects, production_system=self)
                            print(f'Moved objects {str(moved_objects)} to the output buffer {str(output_idx1)}')

                            # Every time an operation is finished and its product is moved to a physical output buffer,
                            # a PickupRequest for this product should be generated.
                            # Waiting for the buffers to block isn't reasonable.
                            
                            # If the product was moved to an "identical" output buffer, no PickupRequest is needed
                            if workstation.physical_output_buffers[output_idx1].identical_buffer == '':
                                print('There are no buffers identical to it, creating PickupRequests')

                                # Always create separate PickupRequests for components
                                #for x in range(len(_finished_ops)):
                                self.event_queue.append(PickupRequest(timestamp=self.timestamp,
                                                                    workstation=workstation,
                                                                    output_buffer_idx1=output_idx1,
                                                                    objects=moved_objects))
                        else:
                            # The operation product could not be moved to any physical output buffer
                            # This can be due to either insufficient buffer capacity or unmet quantization criteria
                            # This means either bad buffer size specification or some yet tbd fringe cases
                            raise NotImplementedError()

                    # Mark operation(s) as finished
                    decision_needed = False
                    for o in _finished_ops:
                        instances = self.order_progress[o[2]]['product_progress']
                        for instance_data in instances:
                            if instance_data['product_id'] == o[1] and instance_data['product_instance'] == o[3]:
                                instance_data['operation_progress'][o[0]]['status'] = OperationStatus.DONE
                                instance_data['operation_progress'][o[0]]['remaining_work'] = 0

                                print(f'Removing operation {str(o)} from the WIP of workstation {workstation.workstation_id}')
                                workstation.wip_operations.remove(o)

                                # See if any operations of this product instance have become available and push them downstream
                                #all_successor_ops_routed = []  # flag to see whether the corresponding OperationFinishedEvent can be deleted

                                op_prog = instance_data['operation_progress']
                                for operation_id in op_prog.keys():
                                    operation = self.find_operation_by_name(operation_id, self.product_operations[o[1]])
                                    # Check whether all of this operation's predecessors have status DONE and if so, find all eligible workstations.
                                    if (op_prog[operation_id]['status'] == OperationStatus.IN_BACKLOG and
                                        all([op_prog[predecessor]['status'] == OperationStatus.DONE for predecessor in op_prog[operation_id]['predecessors']])):
                                        print(f'Operation {operation_id} can be processed now since all its predecessors are finished')
                                        eligible_workstations = self.eligible_workstations_for_operation(operation)

                                        if self.push_operation_downstream(operation_id=operation_id,
                                                                        product_id=o[1],
                                                                        order_id=o[2],
                                                                        product_instance=o[3],
                                                                        eligible_workstations=eligible_workstations,
                                                                        operation_progress=op_prog):
                                            decision_needed = True
                                            break
                                        
                                
                                if decision_needed:
                                    break

                        if decision_needed:
                            break

                    if decision_needed:
                        return True
                    
                    elif not decision_needed:
                        #if all(all_successor_ops_routed):

                        print(f'All successor operations of {str(finished_op)} have been routed, removing OperationFinishedEvent')
                        self.event_queue.remove(earliest_event)

                        # Search for OperationFinishedEvents that can be removed and WorkstationSequencingPostponed that can be re-triggered
                        # for event in copy(self.event_queue):
                        #     # An operation can be finished only at a single workstation and at a single timestamp:
                        #     if isinstance(event, OperationFinishedEvent) and o == event.operation_id:
                        #         # Remove this OperationFinishedEvent
                        #         self.event_queue.remove(event)
                        #         break  # to delete only the OperationFinishedEvent from the current iteration

                        # The O-WIP (wip_operations) needs to be emptied of all (batch) operations before new operations can be committed to.
                        if len(workstation.wip_operations) > 0:
                            continue

                        # With empty O-WIP the workstation is not BUSY anymore.
                        workstation.status.remove(WorkstationStatus.BUSY)
                        
                        # Retrigger postponed workstation sequencing
                        for wsp_event in self.event_queue:
                            if isinstance(wsp_event, WorkstationSequencingPostponed):
                                if wsp_event.workstation is None:
                                    # Such WorkstationSequencingPostponed will be removed
                                    # in the end of the main loop (cleaning). Ignore it here.
                                    continue
                                if wsp_event.workstation.workstation_id == workstation.workstation_id:
                                    print(f'\n... Handling WorkstationSequencingPostponed at {wsp_event.workstation.workstation_id}')
                                    
                                    # As a flag that this WorkstationSequencingPostponed can be deleted:
                                    wsp_event.workstation = None

                                    return self.push_operation_downstream(operation_id=None,
                                                                product_id=None,
                                                                order_id=None,
                                                                product_instance=None,
                                                                eligible_workstations=[workstation.workstation_id],
                                                                operation_progress=None,
                                                                postponed=True)
 

                elif isinstance(earliest_event, SetupFinishedEvent):
                    workstation : Workstation = earliest_event.workstation
                    print(f'\nHandling SetupFinishedEvent at workstation {workstation.workstation_id}')
                    if WorkstationStatus.SETUP in workstation.status:
                        print('    Removed SETUP from workstation status list.')
                        workstation.status.remove(WorkstationStatus.SETUP)
                        workstation.log_status_change(self.timestamp)
                    if workstation.seized_worker != '':
                        print(f'    Seized worker: {workstation.seized_worker}')
                        self.workers[workstation.seized_worker].status = WorkerStatus.IDLE
                        print('    Set worker status to IDLE.')
                        self.workers[workstation.seized_worker].log_status_change(self.timestamp)
                        self.event_queue.append(WorkerReleaseEvent(timestamp=self.timestamp,
                                                       workstation=workstation,
                                                       worker=self.workers[workstation.seized_worker]))
                    # Get operation(s) with status COMMITTED in the workstation's O-WIP
                    for operation in workstation.wip_operations:
                        operation_id, product_id, order_id, product_instance = operation  # tuple with 4 strings
                        product_progress = self.order_progress[order_id]['product_progress']
                        for instance_data in product_progress:
                            if instance_data['product_id'] == product_id and instance_data['product_instance'] == product_instance:
                                if instance_data['operation_progress'][operation_id]['status'] == OperationStatus.COMMITTED:
                                    print(f'    Found an operation with status COMMITTED in the workstation WIP: {str(operation)}')
                                    self.event_queue.remove(earliest_event)
                                    print('    Removed SetupFinishedEvent from event queue.')
                                    print('    Trying to work on operation...')
                                    self.work_on_operation(operation_id, product_id, order_id, product_instance, instance_data['operation_progress'], workstation)

                elif isinstance(earliest_event, WorkerStationArrivalEvent):
                    workstation : Workstation = earliest_event.workstation
                    worker : Worker = earliest_event.worker
                    print(f'\nHandling WorkerStationArrivalEvent')
                    print(f'    worker: {worker.worker_id if worker else ''}')
                    print(f'    workstation {workstation.workstation_id}')
                    if worker:
                        workstation.seized_worker = worker.worker_id
                        worker.location = workstation.workstation_id
                        worker.destination = ''
                        self.workers[workstation.seized_worker].status = WorkerStatus.IDLE
                        self.workers[workstation.seized_worker].log_status_change(self.timestamp)
                    if WorkstationStatus.WAITING_FOR_WORKER in workstation.status:
                        workstation.status.remove(WorkstationStatus.WAITING_FOR_WORKER)
                    handled = False
                    # Get operation(s) with status COMMITTED in the workstation's O-WIP
                    for operation in workstation.wip_operations:
                        operation_id, product_id, order_id, product_instance = operation  # tuple with 4 strings
                        product_progress = self.order_progress[order_id]['product_progress']
                        for instance_data in product_progress:
                            if instance_data['product_id'] == product_id and instance_data['product_instance'] == product_instance:
                                if instance_data['operation_progress'][operation_id]['status'] == OperationStatus.COMMITTED:
                                    print(f'    Found an operation with status COMMITTED in the workstation WIP: {str(operation)}')
                                    self.event_queue.remove(earliest_event)
                                    print('    Removed WorkerStationArrivalEvent from event queue.')
                                    print('    Trying to work on operation...')
                                    self.work_on_operation(operation_id,
                                                           product_id,
                                                           order_id,
                                                           product_instance,
                                                           instance_data['operation_progress'],
                                                           workstation,
                                                           auto_setup=False if worker else True)
                                    # Make sure that the same WorkerStationArrivalEvent doesn't get used by multiple operations in a batch
                                    handled = True
                                    break
                        if handled:
                            break
                    if not handled:
                        print('    Found no committed operations in workstation WIP.')
                        self.event_queue.remove(earliest_event)
                        print('    Removed WorkerStationArrivalEvent.')

                elif isinstance(earliest_event, MaterialsArrivalEvent):
                    workstation : Workstation = earliest_event.workstation
                    print('\nHandling MaterialsArrivalEvent')
                    print(f'    materials: {str(earliest_event.component_dict)}')
                    print(f'    at workstation: {workstation.workstation_id}')
                    print(f'    current input operation buffer: {str(workstation.input_operation_buffer)}')
                    print(f'    current WIP operations: {str(workstation.wip_operations)}')
                    print(f'    current physical input buffer contents: {str([b.contents for b in workstation.physical_input_buffers.values()])}')
                    print(f'    current physical WIP components: {str(workstation.wip_components)}')

                    # Idea: check whether the workstation can take the delivered components using a "test clone"
                    test_clone_ws = deepcopy(workstation)
                    material_put_in_buffer = test_clone_ws.take_objects_into_physical_input_buffers([{'Component': c, 'Quantity': q} for c, q in earliest_event.component_dict.items()])
                    req_num = 1

                    if not material_put_in_buffer:
                        print('    Materials could not be taken in by the workstation input buffers.')
                        # Since MaterialsArrivalEvents are generated only at compatible inventories and buffers,
                        # this case will only occur due to overflowing raw material inventories
                        # or unmet quantization criteria.
                        # In case of quantity steps other than 1 try finding at least qty_step pending
                        # MaterialsArrivalEvents at this workstation with same components and try handling them at once.
                        pending = []
                        for _e in self.event_queue:
                            if isinstance(_e, MaterialsArrivalEvent):
                                if _e.workstation == earliest_event.workstation and _e.component_dict == earliest_event.component_dict:
                                    pending.append(_e)
                        # This is a very inefficient approach, but it seems to ensure possible buffer quantization requirements.
                        # Idea is to try to put the maximum amount of pending deliveries in the input buffers
                        # and retry with smaller amounts until it is successful.
                        test_clone_ws_2 = deepcopy(workstation)
                        for i in reversed(range(1, len(pending) + 1)):
                            trial_components = [{'Component': c, 'Quantity': q * i} for c, q in earliest_event.component_dict.items()]
                            material_put_in_buffer = test_clone_ws_2.take_objects_into_physical_input_buffers(trial_components)
                            if material_put_in_buffer:
                                req_num = i
                                print('    Trying with more of the same materials from pending deliveries worked!')
                                pending_events_slice = pending[:i]
                                for pe in pending_events_slice:
                                    self.event_queue.remove(pe)
                                break
                        if not material_put_in_buffer:
                            print('    The buffer is already full, could not put material in buffer.')
                            earliest_event.buffer_overflow = True
                    
                    if material_put_in_buffer:
                        print('    Finally moving a fitting quantity into physical input buffers...')
                        workstation.take_objects_into_physical_input_buffers([{'Component': c, 'Quantity': q * req_num} for c, q in earliest_event.component_dict.items()], self.timestamp)
                        handled = False
                        # Get operation(s) with status COMMITTED in the workstation's O-WIP
                        for operation in workstation.wip_operations:
                            operation_id, product_id, order_id, product_instance = operation  # tuple with 4 strings
                            product_progress = self.order_progress[order_id]['product_progress']
                            for instance_data in product_progress:
                                if instance_data['product_id'] == product_id and instance_data['product_instance'] == product_instance:
                                    if instance_data['operation_progress'][operation_id]['status'] == OperationStatus.COMMITTED:
                                        print(f'    Found an operation with status COMMITTED in the workstation WIP: {str(operation)}')
                                        # In case of multiple MaterialsArrivalEvents bundled they were all already removed from the event queue
                                        try:
                                            self.event_queue.remove(earliest_event)
                                            print('    Removed MaterialsArrivalEvent from event queue.')
                                        except ValueError:
                                            print('Warning: Tried to remove a MaterialsArrivalEvent that is not there.')
                                        print('    Trying to work on operation...')
                                        self.work_on_operation(operation_id, product_id, order_id, product_instance, instance_data['operation_progress'], workstation)
                                        # Make sure that the same MaterialsArrivalEvent doesn't get used by multiple operations in a batch
                                        handled = True
                                        break
                            if handled:
                                break
                            elif not handled:
                                try:
                                    self.event_queue.remove(earliest_event)
                                    print('    Removed MaterialsArrivalEvent from event queue.')
                                except ValueError:
                                    print('Warning: Tried to remove a MaterialsArrivalEvent that is not there.')

                elif isinstance(earliest_event, RawMaterialArrivalEvent):
                    inventory : Inventory = earliest_event.inventory
                    print(f'\nHandling RawMaterialArrivalEvent of materials {str(earliest_event.component_dict)} at inventory {inventory.inventory_id}')
                    print(f'    current inventory contents: {str(inventory.contents)}')
                    list_of_comp_qty_dicts = [{'Component': k, 'Quantity': v} for k,v in earliest_event.component_dict.items()]
                    is_delivered = inventory.take_objects(list_of_comp_qty_dicts)
                    if not is_delivered:
                        earliest_event.rmi_overflow = True
                    elif is_delivered:
                        if inventory.identical_buffer:
                            buffer_chunks = inventory.identical_buffer.split(" : ")
                            ws_id = buffer_chunks[0]
                            #idx1 = buffer_chunks[2]
                            self.workstations[ws_id].take_objects_into_physical_input_buffers(list_of_comp_qty_dicts)
                        self.event_queue.remove(earliest_event)
                    
                elif isinstance(earliest_event, ToolArrivalEvent):
                    workstation : Workstation = earliest_event.workstation
                    tool : Tool = earliest_event.tool
                    print(f'\nHandling ToolArrivalEvent of tool {tool.tool_id} at workstation {workstation.workstation_id}')
                    workstation.seized_tools.append(tool.tool_id)
                    handled = False
                    # Get operation(s) with status COMMITTED in the workstation's O-WIP
                    for operation in workstation.wip_operations:
                        operation_id, product_id, order_id, product_instance = operation  # tuple with 4 strings
                        product_progress = self.order_progress[order_id]['product_progress']
                        for instance_data in product_progress:
                            if instance_data['product_id'] == product_id and instance_data['product_instance'] == product_instance:
                                if instance_data['operation_progress'][operation_id]['status'] == OperationStatus.COMMITTED:
                                    print(f'    Found an operation with status COMMITTED in the workstation WIP: {str(operation)}')
                                    self.event_queue.remove(earliest_event)
                                    print('    Removed ToolArrivalEvent from event queue.')
                                    print('    Trying to work on operation...')
                                    self.work_on_operation(operation_id, product_id, order_id, product_instance, instance_data['operation_progress'], workstation)
                                    # Make sure that the same ToolArrivalEvent doesn't get deleted by multiple operations in a batch
                                    handled = True
                                    break
                        if handled:
                            break

                elif isinstance(earliest_event, ToolReleaseEvent):
                    workstation : Workstation = earliest_event.workstation
                    tool : Tool = earliest_event.tool
                    print(f'\nHandling ToolReleaseEvent of tool {tool.tool_id} from workstation {workstation.workstation_id}')
                    # If it is a permanent tool of this workstation, nothing needs to be done as that list isn't manipulated, just read.
                    # If it is not a permanently assigned tool, put it back to its tool pool of origin.
                    if tool.tool_id not in workstation.permanent_tools:
                        tool_pool_of_origin = [tp for tp in workstation.allowed_tool_pools if tool.tool_id in self.tool_pools[tp]][0]
                        self.tool_pool_tracker[tool_pool_of_origin].append(tool.tool_id)
                        workstation.tools_in_use.remove(tool.tool_id)
                        print(f'    Removed {tool.tool_id} from workstation tools in use.')
                        # This will trigger re-handling of the first pending ToolsRequest that wants this tool
                        # by setting its some_unavailable_tool_released flag to True
                        # which will then be detected in the beginning of the main event loop.
                        for _e in self.event_queue():
                            if isinstance(_e, ToolsRequest):
                                if tool.tool_id in _e.tools.keys():
                                    print(f'    Found a pending ToolsRequest that requests tool {tool.tool_id}')
                                    _e.some_unavailable_tool_released = True
                                    break

                elif isinstance(earliest_event, WorkerReleaseEvent):
                    workstation : Workstation = earliest_event.workstation
                    worker : Worker = earliest_event.worker
                    print(f'\nHandling WorkerReleaseEvent of worker {worker.worker_id} from workstation {workstation.workstation_id}')
                    if not workstation.permanent_worker_assignment:
                        wp_of_origin = [wp for wp in workstation.allowed_worker_pools if worker.worker_id in self.worker_pools[wp]][0]
                        self.worker_pool_tracker[wp_of_origin].append(worker.worker_id)
                        workstation.seized_worker = ''
                        print(f'    Workstation {workstation.workstation_id} has no seized workers now.')
                        # Try handling the first pending WorkerCapabilitiesRequest that asks for this worker.
                        for _e in self.event_queue:
                            if isinstance(_e, WorkerCapabilitiesRequest):
                                # See what workers the target workstation or transport machine has access to
                                accessible_wps = [self.worker_pools[wp] for wp in _e.target.allowed_worker_pools]
                                accessible_worker_ids = []
                                for wp in accessible_wps:
                                    for wid in wp:
                                        accessible_worker_ids.append(wid)
                                # If the released worker belongs to that set of accessible workers,
                                # retry handling WorkerCapabilitiesRequest in the next iteration
                                if all([set(_e.capability_list).issubset(set(worker.provided_capabilities)),
                                       worker.worker_id in accessible_worker_ids]):
                                    print(f'    Found a pending WorkerCapabilitiesRequest that requests the same capabilities as the released worker.')
                                    _e.some_worker_released = True
                                    # TODO: validate on a schedule that worker capacity constraint influences how setup operations are executed.
                                    _e.timestamp = self.timestamp
                                    break
                    self.event_queue.remove(earliest_event)


                elif isinstance(earliest_event, WorkstationPickupEvent):
                    workstation : Workstation = earliest_event.workstation
                    print(f'\nHandling WorkstationPickupEvent at workstation {workstation.workstation_id}')
                    # Get operation(s) with status COMMITTED in the workstation's O-WIP
                    # to check whether their processing can be started due to possible unblocking of output buffers.
                    for operation in workstation.wip_operations:
                        operation_id, product_id, order_id, product_instance = operation  # tuple with 4 strings
                        product_progress = self.order_progress[order_id]['product_progress']
                        for instance_data in product_progress:
                            if instance_data['product_id'] == product_id and instance_data['product_instance'] == product_instance:
                                if instance_data['operation_progress'][operation_id]['status'] == OperationStatus.COMMITTED:
                                    print(f'    Found an operation with status COMMITTED in the workstation WIP: {str(operation)}')
                                    print('    Trying to work on operation...')
                                    self.work_on_operation(operation_id, product_id, order_id, product_instance, instance_data['operation_progress'], workstation)
                    self.event_queue.remove(earliest_event)
                    print('    Removed WorkstationPickupEvent.')

                elif isinstance(earliest_event, MaterialsRequest):
                    # Unpack the request
                    component_dict = earliest_event.component_dict
                    target_workstation = earliest_event.target_workstation
                    order_id = earliest_event.order_id
                    print('\nHandling MaterialsRequest')
                    print(f'    requested components: {str(component_dict)}')
                    print(f'    target workstation: {target_workstation.workstation_id}')
                    print(f'    order ID: {order_id}')

                    # Compare with MaterialsRequest handled directly before this.
                    # If the same workstation sends the request and the same components (dict keys) are requested,
                    # then the materials aren't available. Generate RawMaterialArrivalEvents again.
                    override_material_available = False
                    if self.last_materials_request:
                        if (self.last_materials_request.target_workstation.workstation_id == earliest_event.target_workstation.workstation_id and
                            self.last_materials_request.component_dict.keys() == earliest_event.component_dict.keys()):
                            override_material_available = True

                    # Get or order raw materials
                    for material in deepcopy(list(component_dict.keys())):

                        if material in self.raw_material_names:

                            supply_behaviour : SupplyBehaviour = self.supply_behaviours[material]
                            # Find a raw metrial inventory where this material can be acquired from.
                            # In case of batch processing machines (and thus workstations)
                            # it can be that multiple operations need to be bundled before
                            # their total requested component amount is divisible by quantity step
                            # of the source inventory. For that case ignore quantity step of the inventory
                            # using the ignore_qty_step argument.
                            ignore_qty_step = False
                            if target_workstation.machine:
                                if self.machines[target_workstation.machine].batch_processing:
                                    ignore_qty_step = True
                            source_inventory, material_available = self.get_source_inventory_with_materials(materials_tuple=(material, component_dict[material]),
                                                                                                            ignore_qty_step=ignore_qty_step)
                            
                            if override_material_available:
                                material_available = False

                            self.last_materials_request = deepcopy(earliest_event)

                            if source_inventory is None:
                                    print(f"There are no sources for material {material} in the required quantity {component_dict[material]} in the system.")
                                    raise RuntimeError()
                            
                            if supply_behaviour.allocation_type == SupplyAllocationType.ORDER_ANONYMOUS:

                                if source_inventory:  # and not material_available - doesn't seem to be necessary - just follow the probability distribution!

                                    if numpy.random.random() <= supply_behaviour.immediate_probability:
                                        # Although the material hasn't been there,
                                        # supply behaviour of this material gives a probability
                                        # of getting it immediately, and we are lucky.

                                        if not source_inventory.identical_buffer:
                                            # Appendleft because first raw materials need to be put into inventory
                                            # and only then should the transport order be executed.
                                            # This is especially important when transport times are 0.
                                            self.event_queue.appendleft(RawMaterialArrivalEvent(timestamp=self.timestamp,
                                                                                        inventory=source_inventory,
                                                                                        component_dict={material: component_dict[material]},
                                                                                        order_id=''))
                                            

                                            # Materials can then be picked up
                                            self.event_queue.appendleft(TransportOrder(timestamp=self.timestamp, component_dict={material: deepcopy(component_dict[material])},
                                                    source=source_inventory, destination=target_workstation))
                                            
                                        elif source_inventory.identical_buffer:
                                            identical_buffer_str_split = source_inventory.identical_buffer.split(' : ')
                                            other_workstation_id = identical_buffer_str_split[0]
                                            other_workstation = self.workstations[other_workstation_id]
                                            self.event_queue.append(MaterialsArrivalEvent(timestamp=self.timestamp,
                                                                    workstation=other_workstation,
                                                                    component_dict={material: component_dict[material]}))
                                            
                                        # Trigger MaterialsRequest deletion
                                        earliest_event.component_dict.pop(material)
                                        #self.event_queue.remove(earliest_event)
                                    else:
                                        # Generate a RawMaterialArrival event in the future
                                        # according to the supply behaviour probability distribution.
                                        supply_time = numpy.random.gamma(supply_behaviour.alpha, supply_behaviour.beta) + supply_behaviour.min
                                        supply_time = self.get_int_seconds(supply_time, supply_behaviour.time_unit)
                                        self.event_queue.append(RawMaterialArrivalEvent(timestamp=self.timestamp + supply_time,
                                                                                        inventory=source_inventory,
                                                                                        component_dict={material: component_dict[material]},
                                                                                        order_id=''))
                                        # Move MaterialsRequest in the future to the delivery
                                        earliest_event.timestamp = self.timestamp + supply_time

                            if supply_behaviour.allocation_type == SupplyAllocationType.ORDER_SPECIFIC:
                                # TODO Consult previous ORDER_ANONYMOUS case for example how to implement this!
                                raise NotImplementedError()
                                if source_inventory is not None and material_available == False:
                                    if numpy.random.random() <= supply_behaviour.immediate_probability:
                                        # Although the material hasn't been there,
                                        # supply behaviour of this material gives a probability
                                        # of getting it immediately, and we are lucky.
                                        if source_inventory.identical_buffer == '':
                                            self.event_queue.append(TransportOrder(timestamp=self.timestamp, component_dict={material: deepcopy(component_dict[material])},
                                                    source=source_inventory, destination=target_workstation))
                                        elif source_inventory.identical_buffer != '':
                                            identical_buffer_str_split = source_inventory.identical_buffer.split(' : ')
                                            other_workstation_id = identical_buffer_str_split[0]
                                            other_workstation = self.workstations[other_workstation_id]
                                            # Note: order-specific MaterialsArrivalEvent here, order ID is specified
                                            self.event_queue.append(MaterialsArrivalEvent(timestamp=self.timestamp,
                                                                    workstation=other_workstation,
                                                                    component_dict={material: component_dict[material]},
                                                                    order_id=order_id))
                                        earliest_event.component_dict.pop(material)
                                        #self.event_queue.remove(earliest_event)
                                    else:
                                        # Raw materials need to be ordered.
                                        # Generate a RawMaterialArrival event in the future
                                        # according to the supply behaviour probability distribution.
                                        supply_time = numpy.random.gamma(supply_behaviour.alpha, supply_behaviour.beta) + supply_behaviour.min
                                        supply_time = self.get_int_seconds(supply_time, supply_behaviour.time_unit)
                                        # Note: order-specific MaterialsArrivalEvent here, order ID is specified
                                        self.event_queue.append(RawMaterialArrivalEvent(timestamp=self.timestamp + supply_time,
                                                                                        inventory=source_inventory,
                                                                                        component_dict={material: component_dict[material]},
                                                                                        order_id=order_id))
                                        # Move MaterialsRequest in the future to the delivery
                                        earliest_event.timestamp = self.timestamp + supply_time
                                if source_inventory is not None and material_available == True:
                                    # We need to check whether the material was meant for the current MaterialsRequest.
                                    # That means there is a RawMaterialArrivalEvent at the same timestamp with a matching order ID.
                                    matching_order = False
                                    event_to_delete = None
                                    for e in self.event_queue:
                                        if e.timestamp == earliest_timestamp and isinstance(e, RawMaterialArrivalEvent):
                                            if e.order_id == earliest_event.order_id and e.component_dict.keys()[0] == material:
                                                matching_order = True
                                                event_to_delete = e
                                                break
                                    if matching_order:
                                        self.event_queue.remove(event_to_delete)
                                        if source_inventory.identical_buffer == '':
                                            self.event_queue.append(TransportOrder(timestamp=self.timestamp, component_dict={material: component_dict[material]},
                                                    source=source_inventory, destination=target_workstation))
                                        elif source_inventory.identical_buffer != '':
                                            identical_buffer_str_split = source_inventory.identical_buffer.split(' : ')
                                            other_workstation_id = identical_buffer_str_split[0]
                                            other_workstation = self.workstations[other_workstation_id]
                                            # Note: order-specific MaterialsArrivalEvent here, order ID is specified
                                            self.event_queue.append(MaterialsArrivalEvent(timestamp=self.timestamp,
                                                                    workstation=other_workstation,
                                                                    component_dict={material: component_dict[material]},
                                                                    order_id=order_id))
                                        earliest_event.component_dict.pop(material)
                                        #self.event_queue.remove(earliest_event)
                                    # TODO: I suspect that the opposite case can never happen because we have moved
                                    # the order-specific MaterialsRequest exactly to the same timestamp as the delivery date...
                                    # However, pay attention to this while debugging...

                            # Remove MaterialsRequest event if no components left unhandled
                            if earliest_event.component_dict == {}:
                                self.event_queue.remove(earliest_event)
                                print(f'\n### Removed an empty MaterialsRequest from {earliest_event.target_workstation.workstation_id}')

                        if material not in self.raw_material_names:

                            # In case of internally created materials, search for any pending PickupRequests with components matching MaterialsRequest
                            for e in self.event_queue:
                                if e.timestamp <= earliest_event.timestamp and isinstance(e, PickupRequest):
                                    if e.objects[0]['Component'] == material and e.objects[0]['Quantity'] >= component_dict[material]:
                                        # Create TransportOrder (in case of identical buffers a MaterialsArrivalEvent is directly created, and no PickupRequests)
                                        self.event_queue.appendleft(TransportOrder(timestamp=self.timestamp,
                                                                               component_dict={material: deepcopy(component_dict[material])},
                                                                               source=(e.workstation, e.workstation.physical_output_buffers[e.output_buffer_idx1]),
                                                                               destination=earliest_event.target_workstation))
                                        e.objects[0]['Quantity'] -= component_dict[material]
                                        self.event_queue.remove(earliest_event)
                                        break
                
                elif isinstance(earliest_event, TransportOrder):
                    print(f'\nHandling TransportOrder')
                    print(f'    components: {str(earliest_event.component_dict)}')
                    # Make a list of all TransportMachines IDs that are technically capable of this TransportOrder
                    eligible_transport = []
                    for transport_id, transport_machine in self.transport_machines.items():
                        if transport_machine.batch_processing:
                            # Check whether the batch size specification allows all required components in desired quantities
                            components_fit = []
                            for component, quantity in earliest_event.component_dict.items():
                                # Check whether the transport machine is generally fit to transport this component in this quantity (assuming it's empty)
                                if transport_machine.accepts_objects(objects=(component, quantity), wip_components=[]):  # wip_components=transport_machine.payload
                                    components_fit.append(True)
                                else:
                                    components_fit.append(False)
                            if all(components_fit):
                                eligible_transport.append(transport_id)
                        if not transport_machine.batch_processing:
                            raise NotImplementedError()
                    # Get a string representation of the source
                    source = ''
                    if isinstance(earliest_event.source, Workstation):
                        source = earliest_event.source.workstation_id
                    if isinstance(earliest_event.source, Inventory):
                        source = earliest_event.source.inventory_id
                    if isinstance(earliest_event.source, tuple):
                        source = earliest_event.source[0].workstation_id
                    print(f'    source: {source}')
                    # Get a string representation of the destination
                    destination = ''
                    if isinstance(earliest_event.destination, Workstation):
                        destination = earliest_event.destination.workstation_id
                    if isinstance(earliest_event.destination, Inventory):
                        destination = earliest_event.destination.inventory_id
                    if isinstance(earliest_event.destination, tuple):
                        destination = earliest_event.destination[0].workstation_id
                    print(f'    destination: {destination}')
                    # Handle transport order, i.e. trigger TRANSPORT_ROUTING or TRANSPORT_SEQUENCING
                    self.event_queue.remove(earliest_event)
                    return self.handle_transport_order(earliest_event.component_dict, source, destination, eligible_transport)
                    
                elif isinstance(earliest_event, LoadingFinishedEvent):
                    print(f'\nHandling LoadingFinishedEvent of transport machine {earliest_event.transport_machine.machine_id}')
                    earliest_event.transport_machine.status.remove(TransportMachineStatus.LOADING)
                    earliest_event.transport_machine.status.append(TransportMachineStatus.READY)
                    # Remove the objects from the workstation's output buffers or the inventory
                    if isinstance(earliest_event.location, Workstation):
                        earliest_event.location.remove_objects_from_output_buffers(earliest_event.objects, self.timestamp)
                        # ...while creating a WorkstationPickupEvent - to signal that maybe blocking was resolved;
                        self.event_queue.append(WorkstationPickupEvent(timestamp=self.timestamp,
                                                                        workstation=earliest_event.location))
                    if isinstance(earliest_event.location, Inventory):
                        earliest_event.location.remove_objects(earliest_event.objects)
                        # This should trigger retrying the first pending RawMaterialArrivalEvent at this inventory
                        # if there was a raw material inventory (RMI) overflow.
                        for _e in self.event_queue:
                            if isinstance(_e, RawMaterialArrivalEvent):
                                if _e.inventory == earliest_event.location and _e.rmi_overflow:
                                    _e.rmi_overflow = False
                                    break

                    # Get a string representation of the source
                    source = ''
                    if isinstance(earliest_event.location, Workstation):
                        source = earliest_event.location.workstation_id
                    if isinstance(earliest_event.location, Inventory):
                        source = earliest_event.location.inventory_id
                    if isinstance(earliest_event.location, tuple):
                        source = earliest_event.location[0].workstation_id
                    self.event_queue.remove(earliest_event)
                    self.execute_transport_order(material_source=source, transport_machine=earliest_event.transport_machine)

                elif isinstance(earliest_event, TransportArrivalEvent):
                    transport_machine : TransportMachine = earliest_event.transport_machine
                    location = earliest_event.destination.workstation_id if isinstance(earliest_event.destination, Workstation) else earliest_event.destination.inventory_id
                    transport_machine.current_location = location
                    print(f'\nHandling TransportArrivalEvent of transport machine {transport_machine.machine_id} at {location}')
                    if TransportMachineStatus.LOADING in transport_machine.status:
                        # Should only be the case on simulation start when transport machines are "spawned" at their first pickup location.
                        # A LoadingFinishedEvent should have been already created.
                        self.event_queue.remove(earliest_event)
                    if TransportMachineStatus.MOVING_TO_SOURCE in transport_machine.status:
                        # Transport machine simply arrived at the source where it will collect the materials from a committed transport order
                        transport_machine.status.remove(TransportMachineStatus.MOVING_TO_SOURCE)
                        self.event_queue.remove(earliest_event)
                        self.execute_transport_order(material_source=location, transport_machine=transport_machine)
                    if TransportMachineStatus.EXECUTING_TRANSPORT in transport_machine.status:
                        # Transport machine arrived at the target with materials, take care of unloading and announcing materials arrival.
                        transport_machine.status.remove(TransportMachineStatus.EXECUTING_TRANSPORT)
                        transport_machine.status.append(TransportMachineStatus.UNLOADING)
                        self.event_queue.remove(earliest_event)
                        self.execute_transport_order(material_source=transport_machine.departed_from, transport_machine=transport_machine)

                elif isinstance(earliest_event, UnloadingFinishedEvent):
                    print(f'\nHandling UnloadingFinishedEvent of transport machine {earliest_event.transport_machine.machine_id}')
                    transport_machine : TransportMachine = earliest_event.transport_machine
                    objects_to_remove = earliest_event.objects
                    transport_machine.status.remove(TransportMachineStatus.UNLOADING)
                    transport_machine.status.append(TransportMachineStatus.IDLE)
                    if earliest_event.location in self.workstations.keys():
                        workstation : Workstation = self.workstations[earliest_event.location]
                        # Create a MaterialsArrivalEvent at the workstation
                        self.event_queue.append(MaterialsArrivalEvent(timestamp=self.timestamp,
                                                                      workstation=workstation,
                                                                      component_dict={objects_to_remove[0]['Component']: objects_to_remove[0]['Quantity']}))
                    if earliest_event.location in self.inventories.keys():
                        inventory : Inventory = self.inventories[earliest_event.location]
                        unloaded = inventory.take_objects(objects=objects_to_remove)
                        if not unloaded:
                            print(f"Target inventory {inventory.inventory_id} does not accept materials: {objects_to_remove}")
                            raise RuntimeError()
                    # Remove materials from transport machine payload
                    temp_payload = deepcopy(transport_machine.payload)
                    for payload_item in temp_payload:
                        if payload_item['Component'] == objects_to_remove[0]['Component']:
                            if payload_item['Quantity'] >= objects_to_remove[0]['Quantity']:
                                payload_item['Quantity'] -= objects_to_remove[0]['Quantity']
                            else:
                                # Attention: there are sometimes comp-qty dicts with qty=0 left over, erase them
                                if payload_item['Quantity'] == 0:
                                    transport_machine.payload.remove(payload_item)
                                    continue
                                print(f"Cannot remove {objects_to_remove[0]} from {transport_machine.machine_id}, there aren't so many components in the payload!")
                                raise RuntimeError()
                            break
                    # Rewrite transport machine payload after possible deletions, erase empty payload items directly
                    transport_machine.payload = [temp_payload[i] for i in range(len(temp_payload)) if temp_payload[i]['Quantity'] > 0]
                    # Remove this transport order from the transport order list
                    delivered_quantity = 0
                    for transport_item in transport_machine.transport_order_list:
                        if all([transport_item['Component'] == objects_to_remove[0]['Component'],
                                transport_item['Destination'] == earliest_event.location,
                                transport_item['Commitment'] == True]):
                            temp_delivered = min(objects_to_remove[0]['Quantity'] - delivered_quantity, transport_item['Quantity'])
                            transport_item['Quantity'] -= temp_delivered
                            delivered_quantity += temp_delivered
                            if delivered_quantity == objects_to_remove[0]['Quantity']:
                                break
                    for transport_item in deepcopy(transport_machine.transport_order_list):
                        if transport_item['Quantity'] == 0:
                            transport_machine.transport_order_list.remove(transport_item)
                    # Directly check how many alternative transport orders are possible and trigger a TRANSPORT_SEQUENCING decision
                    if len(transport_machine.transport_order_list) > 0:
                        # Remove first occurence of TransportSequencingPostponed at this transport machine
                        for _e in copy(self.event_queue):
                            if isinstance(_e, TransportSequencingPostponed):
                                if _e.transport_machine.machine_id == transport_machine.machine_id:
                                    print(f'\n... Handling TransportSequencingPostponed at {transport_machine.machine_id}')
                                    # Remove this TransportSequencingPostponed event
                                    self.event_queue.remove(_e)
                                    # Remove handled UnloadingFinishedEvent
                                    self.event_queue.remove(earliest_event)
                                    # Re-trigger a transport sequencing decision
                                    return self.handle_transport_order(component_dict={},
                                                                       source=None,
                                                                       destination=None,
                                                                       eligible_transport=[transport_machine.machine_id],
                                                                       postponed=True)
                        
                        
                    # Remove handled UnloadingFinishedEvent, no matter if there was a postponed transport sequencing pending or not
                    self.event_queue.remove(earliest_event)

                elif isinstance(earliest_event, ToolsRequest):
                    target_workstation : Workstation = earliest_event.target_workstation
                    print('\nHandling ToolsRequest')
                    print(f'    requested tools: {str(earliest_event.tools)}')
                    print(f'    target workstation: {target_workstation.workstation_id}')
                    # If this ToolsRequest can't be fulfilled at this point,
                    # then we have to leave it in the past until a ToolRelease maybe solves it.
                    earliest_event.just_created = False
                    # Reset the trigger flag so this ToolsRequest stays "inactive"/"in the past" until some relevant tool gets released
                    if earliest_event.some_unavailable_tool_released == True:
                        earliest_event.some_unavailable_tool_released = False
                    num_requested_tools = len(earliest_event.tools)
                    tools_found = []
                    # Look for requested tools in the workstation's allowed tool pools
                    for tool_pool_id in target_workstation.allowed_tool_pools:
                        for tool_id in deepcopy(self.tool_pool_tracker[tool_pool_id]):
                            if tool_id in earliest_event.tools.keys():
                                # A tool with a matching ID has been found, move it into "seized tools" of the workstation
                                target_workstation.seized_tools.append(tool_id)
                                # Remove this tool from the dynamic tool pool tracker
                                self.tool_pool_tracker[tool_pool_id].remove(tool_id)
                                # The tool is not missing anymore
                                earliest_event.tools.pop(tool_id)
                                # Attention: each tool gets a separate ToolArrivalEvent!
                                self.event_queue.append(ToolArrivalEvent(timestamp=self.timestamp,
                                                                         workstation=target_workstation,
                                                                         tool=self.tools[tool_id]))
                                tools_found.append(True)


                    if len(tools_found) < num_requested_tools:
                        # Not all of the requested tools are available in allowed tool pools of the workstation
                        print(f'Warning: ToolsRequest could not be completed!')
                        print(f'{str(num_requested_tools-len(tools_found))} of {str(num_requested_tools)} tools are not available.')
                            
                elif isinstance(earliest_event, WorkerCapabilitiesRequest):
                    # capabilities = earliest_event.capability_list  # [worker capability names (str)]
                    # target = earliest_event.target  # Workstation or TransportMachine
                    print('\nHandling WorkerCapabilitiesRequest')
                    if isinstance(earliest_event.target, Workstation):
                        target_workstation : Workstation = earliest_event.target
                        print(f'    workstation: {target_workstation.workstation_id}')
                        print(f'    requested capabilities: {earliest_event.capability_list}')

                        # If this WorkerCapabilitiesRequest can't be fulfilled at this point,
                        # then we have to leave it in the past until a WorkerReleaseEvent maybe solves it.
                        earliest_event.just_created = False
                        # Reset the trigger flag so this ToolsRequest stays "inactive"/"in the past" until some relevant tool gets released
                        if earliest_event.some_worker_released == True:
                            earliest_event.some_worker_released = False

                        # Look for a worker with all requested capabilities in the workstation's allowed worker pools
                        worker_found = False
                        # Special cases and missing input handling
                        if not target_workstation.allowed_worker_pools:
                            print('    This is a fully automated workstation (no allowed worker pools).')
                            # It can be that the workstation is fully automated, including setup operations.
                            # In this case ignore the request if an empty list of worker capabilities has been requested.
                            if not earliest_event.capability_list:
                                print('    List of requested capabilities is empty.')
                                if WorkstationStatus.WAITING_FOR_WORKER in target_workstation.status:
                                    target_workstation.status.remove(WorkstationStatus.WAITING_FOR_WORKER)
                                    print('    Removed WAITING_FOR_WORKER from target workstation status.')

                                # Working on operation still needs to be re-triggered by a WorkerStationArrivalEvent with worker=None
                                self.event_queue.append(WorkerStationArrivalEvent(timestamp=self.timestamp,
                                                                                      workstation=target_workstation,
                                                                                      worker=None))
                                self.event_queue.remove(earliest_event)
                                print('    Removed WorkerCapabilitiesRequest.')
                            # If the requested capability list isn't empty, then something is definitely wrong with the input.
                            else:
                                print(f'Error: no allowed worker pools have been specified for target workstation {target_workstation.workstation_id}!')
                                raise RuntimeError()
                        
                        print('    Target workstation has access to worker pools.')
                        for worker_pool_id in target_workstation.allowed_worker_pools:
                            for worker_id in deepcopy(self.worker_pool_tracker[worker_pool_id]):
                                if set(earliest_event.capability_list).issubset(set(self.workers[worker_id].provided_capabilities)):
                                    print(f'    Found worker {worker_id} in the worker pool tracker with requested capabilities.')
                                    worker_found = True
                                    self.workers[worker_id].status = WorkerStatus.WALKING
                                    print('    Set their status to WALKING.')
                                    self.workers[worker_id].destination = target_workstation.workstation_id
                                    print(f'    Set their destination to {target_workstation.workstation_id}.')
                                    self.worker_pool_tracker[worker_pool_id].remove(worker_id)
                                    print(f'    Removed them from the worker pool {worker_pool_id}.')
                                    walking_duration = 0
                                    try:
                                        walking_duration = math.ceil(self.get_distance(self.workers[worker_id].location, self.workers[worker_id].destination) / self.walking_speed)
                                    except KeyError:
                                        pass
                                    print(f'    Calculated walking duration: {str(walking_duration)} s.')
                                    self.event_queue.append(WorkerStationArrivalEvent(timestamp=self.timestamp + walking_duration,
                                                                                      workstation=target_workstation,
                                                                                      worker=self.workers[worker_id]))
                                    self.event_queue.remove(earliest_event)
                                    print('    Removed WorkerCapabilitiesRequest.')
                                    break
                            if worker_found:
                                break

                    if isinstance(earliest_event.target, TransportMachine):
                        target_transport : TransportMachine = earliest_event.target
                        print(f'    transport machine: {target_transport.machine_id}')
                        print(f'    requested capabilities: {earliest_event.capability_list}')
                        # Look for a worker with all requested capabilities in all worker pools
                        worker_found = False
                        for worker_pool_id in self.worker_pools.keys():
                            for worker_id in deepcopy(self.worker_pool_tracker[worker_pool_id]):
                                if set(earliest_event.capability_list).issubset(set(self.workers[worker_id].provided_capabilities)):
                                    worker_found = True
                                    self.workers[worker_id].status = WorkerStatus.WALKING
                                    self.worker_pool_tracker[worker_pool_id].remove(worker_id)
                                    walking_duration = 0
                                    try:
                                        walking_duration = math.ceil(self.get_distance(self.workers[worker_id].location, self.workers[worker_id].destination) / self.walking_speed)
                                    except KeyError:
                                        pass
                                    self.event_queue.append(WorkerTransportArrivalEvent(timestamp=self.timestamp + walking_duration,
                                                                                        transport_machine=target_transport,
                                                                                        worker=self.workers[worker_id]))
                                    self.event_queue.remove(earliest_event)
                                    break
                            if worker_found:
                                break

                elif isinstance(earliest_event, WorkerTransportArrivalEvent):
                    transport_machine : TransportMachine = earliest_event.transport_machine
                    worker : Worker = earliest_event.worker
                    print(f'\nHandling WorkerTransportArrivalEvent')
                    print(f'    worker: {worker.worker_id}')
                    print(f'    transport machine: {transport_machine.machine_id}')
                    transport_machine.seized_worker = worker.worker_id
                    worker.location = transport_machine.current_location
                    worker.destination = ''
                    self.workers[transport_machine.seized_worker].status = WorkerStatus.IDLE
                    # Attention: execute_transport_order() sets "Committed" = True after it was able to bundle materials
                    # On init the transport machine gets "spawned" at the "source" of materials corresponding to TRANSPORT_SEQUENCING decision
                    self.execute_transport_order(material_source=transport_machine.current_location,
                                                 transport_machine=transport_machine)
                    self.event_queue.remove(earliest_event)

                # Placeholder for another Event case handling

                else:
                    # Place for event types that are handled only when triggered by other events.
                    # Example: only OperationFinishedEvent triggers WorkstationSequencingPostponed handling.
                    if isinstance(earliest_event, WorkstationSequencingPostponed):
                        pass
                    # When operations are finished, PickupRequests are generated for each produced component
                    # if there are no identical buffers. When such PickupRequest matches some MaterialsRequest
                    # from elsewhere in the production system, a TransportOrder is created and component quantities
                    # of the PickupRequest get reduced. If the component list of a PickupRequest gets empty,
                    # such PickupRequest is simply removed from from the event queue (s. below).
                    if isinstance(earliest_event, PickupRequest):
                        pass
                    else:
                        print(f'Error: Handling {type(earliest_event).__name__} is not implemented yet')
                        raise NotImplementedError()

                # Event queue cleaning
                for _event in copy(self.event_queue):
                    # any PickupRequests with empty objects list (or any component-quantity dicts with 0 quantity)
                    if isinstance(_event, PickupRequest):
                        if _event.objects == {}:
                            self.event_queue.remove(_event)
                            print(f'\n### Removed an empty PickupRequest from {_event.workstation.workstation_id}')
                        if len(_event.objects) > 0:
                            if _event.objects[0]['Quantity'] == 0:
                                self.event_queue.remove(_event)
                                print(f'\n### Removed an empty PickupRequest from {_event.workstation.workstation_id}')
                    # any ToolsRequests with empty tools list
                    if isinstance(_event, ToolsRequest):
                        if _event.tools == {}:
                            self.event_queue.remove(_event)
                            print(f'\n### Removed an empty ToolsRequest from {_event.target_workstation.workstation_id}')
                    # any WorkstationSequencingPostponed with None as workstation
                    if isinstance(_event, WorkstationSequencingPostponed):
                        if _event.workstation is None:
                            self.event_queue.remove(_event)
                            print('\n### Removed a handled WorkstationSequencingPostponed')
                            #return True

                continue


    def get_obs(self):
        '''Returns the observation of the production system at its current state.
        '''
        raise NotImplementedError()

    def is_done(self):
        '''Returns a boolean whether the current timestamp of the production system has reached the end timestamp as specified in the GUI.
        '''
        if self.timestamp >= self.end_timestamp:
            return True
        else:
            return False
        
    def reset(self):
        '''Returns the production system object into its initial state.
        '''
        raise NotImplementedError()

    def to_dict(self):
        return {
            "worker_capabilities": object_to_dict(self.worker_capabilities),
            "workers": object_to_dict(self.workers),
            "worker_pools": object_to_dict(self.worker_pools),
            "tools": object_to_dict(self.tools),
            "tool_pools": object_to_dict(self.tool_pools),
            "machine_capabilities": object_to_dict(self.machine_capabilities),
            "machines": object_to_dict(self.machines),
            "workstations": object_to_dict(self.workstations),
            "product_instructions": object_to_dict(self.product_instructions),
            "supply_behaviours": object_to_dict(self.supply_behaviours),
            "inventories": object_to_dict(self.inventories),
            "conveyors": object_to_dict(self.conveyors),
            "distance_matrix": object_to_dict(self.distance_matrix),
            "order_list": object_to_dict(self.order_list),
            "start_timestamp": self.start_timestamp,
            "end_timestamp": self.end_timestamp,
            "walking_speed": self.walking_speed,
            "energy_costs": self.energy_costs
        }
