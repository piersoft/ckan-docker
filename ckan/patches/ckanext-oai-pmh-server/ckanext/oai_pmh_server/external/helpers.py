def get_authors(data_dict):
    """Get all authors from agent field in data_dict"""
    return filter(
        lambda x: x.get("role") == "author", data_dict.get("agent", [])
    )


def get_contacts(data_dict):
    """Get all contacts from data_dict"""
    return data_dict.get("contact", [])


def get_distributors(data_dict):
    """Get a all distributors from agent field in data_dict"""
    return filter(
        lambda x: x.get("role") == "distributor", data_dict.get("agent", [])
    )


def get_distributor(data_dict):
    """Get a single distributor from agent field in data_dict"""
    return fn.first(get_distributors(data_dict))


def get_contributors(data_dict):
    """Get a all contributors from agent field in data_dict"""
    return filter(
        lambda x: x.get("role") == "contributor", data_dict.get("agent", [])
    )
