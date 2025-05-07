def object_to_dict(obj):
    if hasattr(obj, "to_dict"):  # Check if the object has a to_dict method
        return obj.to_dict()
    elif isinstance(obj, dict):  # If it's a dictionary, recursively serialize it
        return {key: object_to_dict(value) for key, value in obj.items()}
    elif isinstance(obj, list):  # If it's a list, serialize each element
        return [object_to_dict(item) for item in obj]
    elif isinstance(obj, tuple):  # If it's a tuple, convert to a list
        return [object_to_dict(item) for item in obj]
    else:
        if obj == float("inf"):
            return "inf"
        return obj  # If it's a primitive type, return it directly
