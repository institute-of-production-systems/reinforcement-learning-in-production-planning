def get_legal_actions(self):
        '''Returns all legal actions for the current state of the production system.
        '''

        # It seems like there needs to be a dummy action (-1) in case all available "actions"
        # are trivial, e.g. an operation can only be forwarded/routed to a single workstation due to
        # capability/process constraints. This also seems to be the only case where the alternative
        # of skipping the decision is meaningless - the operation must flow to a designated downstream
        # workstation if there are simply no other techically feasible alternatives!
        # In case of such dummy action (-1), the step function should continue
        # simulating the system until non-trivial decisions need to be made.
        # This should reduce the amount of "trivial" action learning, which shouldn't be done by RL anyway.

        legal_actions = []

        # See what workstation actions are available
        for order_id, order in self.order_list.order_list.items():
            if self.order_progress[order_id]['release_time'] > self.timestamp:
                # The order has not been released to the planning algorithm yet
                continue
            product_progress = self.order_progress[order_id]['product_progress']
            for instance_data in product_progress:
                # Operations without precedence constraints (initial operations) or with all predecessors done
                # can be routed to workstations' IOB. Operations are not routed to inventories since
                # inventories are just storages for materials which are to be requested via a MaterialsRequest.
                product_id = instance_data['product_id']
                product_instance = instance_data['product_instance']
                operation_progress = instance_data['operation_progress']
                for operation_id in operation_progress.keys():
                    operation = self.product_operations[product_id]
                    # Check whether all of this operation's predecessors have status DONE and if so, find all eligible workstations.
                    if (operation_progress[operation_id]['status'] == OperationStatus.IN_BACKLOG and
                        all(predecessor['status'] == OperationStatus.DONE for predecessor in operation_progress[operation_id]['predecessors'])):
                        eligible_workstations = []
                        for workstation_id, workstation in self.workstations.items():
                            # Finding eligible workstations consists of the following steps:
                            # 1. Workstation can provide necessary capabilities
                            # 2. Workstation can provide necessary tools
                            # 3. Workstation's physical input buffers can contain the required components in necessary amounts
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
                            if all(capabilities_possible, tools_possible, materials_possible):
                                eligible_workstations.append(workstation_id)

                        if len(eligible_workstations) == 0:
                            print(f'There are no eligible workstations for {operation_id} of {product_id}!')
                            raise RuntimeError
                        if len(eligible_workstations) == 1:
                            # As per the long comment in the beginning, if there is technically only a single
                            # eligible workstation for this operation, the routing action is trivial and is handled
                            # by the simulation itself and not by the planning algorithm.
                            continue
                        if len(eligible_workstations) > 1:
                            # Routing decision/action required, write 1 to the action_matrix in the corresponding cells
                            i = self.action_matrix_row_dict[operation_id + '|' + product_id + '|' + order_id]
                            for ews in eligible_workstations:
                                j = self.action_matrix_col_dict[ews]
                                self.action_matrix[i][j] = 1


            # for product_id in order.products.keys():
            #     for operation in self.product_operations[product_id]:
            #         row_id = operation.operation_name + '|' + product_id + '|' + order_id

                    # Check for trivial operation routing actions and remove them

        # See what transport actions are available


        for i in range(self.action_matrix_n_rows):
            for j in range(self.action_matrix_n_cols):
                if self.action_matrix[i][j] == 1:
                    legal_actions.append(i * self.action_matrix_n_cols + j)

        return legal_actions