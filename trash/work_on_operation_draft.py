def work_on_operation(self, operation_id, product_id, order_id, product_instance, operation_progress, workstation : Workstation):
        '''
        Gets called once an operation's status is changed to COMMITTED and returns True once the program can continue working on the event queue,
        i.e. all relevant resource requests and other events regarding this operation are created.
        It is a separate function because many event types lead to this part of the simulation logic.
        '''
        # Are all components needed for this operation available in the workstation's physical input buffers or in the physical WIP?
        required_components = {}  # key: component name, value: quantity
        for operation_node in self.product_operations[product_id]:
            if operation_node.operation_name == operation_id:
                required_components = operation_node.components
                break
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
                missing_components[rc] += rq - available_components[rc]

        if not all_components_available:
            if WorkstationStatus.WAITING_FOR_MATERIAL not in workstation.status:
                workstation.status.append(WorkstationStatus.WAITING_FOR_MATERIAL)
            for k,v in missing_components.items():
                self.event_queue.append(MaterialsRequest(timestamp=self.timestamp, component_dict={k:v}, target_workstation=workstation))

        if all_components_available:
            # Move all required components that are still in PhIBs, into Ph-WIP (wip_components)
            # See what is already in the wip_components
            components_available_in_wip = {}
            for d in workstation.wip_components:
                components_available_in_wip.update({d['Component'], d['Quantity']})
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
                        if phib.sequence_type == BufferSequenceType.FREE:
                            if mq - already_moved_qty > phib.contents[mc]:
                                already_moved_qty += phib.contents[mc]
                                phib.contents.pop(mc)
                                for d in workstation.wip_components:
                                    if d['Component'] == mc:
                                        d['Quantity'] += already_moved_qty
                                        break
                            else:
                                phib.contents[mc] -= mq - already_moved_qty
                                already_moved_qty = mq
                                for d in workstation.wip_components:
                                    if d['Component'] == mc:
                                        d['Quantity'] = mq
                                        break
                    phib_idx += 1
            # Remove "waiting for material" status
            workstation.status.remove(WorkstationStatus.WAITING_FOR_MATERIAL)
            # Remove any related previous MaterialsRequests from this workstation
            for event in self.event_queue:
                if event.isinstance(MaterialsRequest):
                    if event.target_workstation == workstation and event.timestamp < self.timestamp:
                        # If the materials requested within this event are already in wip_components,
                        # then this MaterialsRequest has been satisfied
                        
                        
        
        # Is the operation completely manual or does it involve a machine?

        