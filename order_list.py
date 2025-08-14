from copy import copy, deepcopy
from file_utils import object_to_dict

class OrderList():
    '''
    Stores all order information from the Order Data tab.
    '''
    def __init__(self, order_list=dict()):
        self.order_list = order_list  # dictionary {order_id: Order}

    def add_order(self, order_id, order):
        print(f"--> Updated order list with order {order_id}")
        self.order_list.update({copy(order_id): copy(order)})
        #print(self.order_list)

    def to_dict(self):
        return {
            "order_list": object_to_dict(self.order_list)
        }

class Order():
    def __init__(self, order_id=None, products=None, release_time=None, deadline=None):
        self.order_id = order_id  # string ID
        self.products = products  # dictionary {product_id: quantity}
        self.release_time = release_time  # date in format %d.%m.%Y %H:%M
        self.deadline = deadline  # date in format %d.%m.%Y %H:%M

    def to_dict(self):
        return {
            "order_id": self.order_id,
            "products": object_to_dict(self.products),
            "release_time": self.release_time,
            "deadline": self.deadline
        }





# TEST
