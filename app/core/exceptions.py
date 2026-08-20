class ServiceException(Exception):
    pass

class NoSuchElementException(ServiceException):
    pass

class ElementAlreadyExistsException(ServiceException):
    pass

class BadCredentialsException(ServiceException):
    pass

class PriceUnavailableException(ServiceException):
    pass