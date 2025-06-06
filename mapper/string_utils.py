import numpy as np
from scipy import optimize

def rm_all(s: str, sep: str = '\n'):
    """

    Parameters
    ----------
    s : str
        str-type condition consisits of one or many lines.
    sep : str
        character used as a separator

    Returns
    -------
    List of single conditions without empty conditions
    
    Example
    -------
    s = 'abc\ndef\n\n'
    sep = '\n'
    
    return -> ['abc', 'def']

    """
    
    conditions = s.split(sep)
    pas = []
    for idx in range(len(conditions)):
        if conditions[idx] == '':
            pass
        elif conditions[idx] == ' ':
            pass
        else:
            pas.append(conditions[idx])
    
    return pas


def condition_2_func(condition: str, slave0: float):
    """
    
    Parameters
    ----------
    condition : str
        str-type condition in a form g(y, x) == f(y, x)
    slave0 : float
        slave point

    Returns
    -------
    function type f1(y)
    
    Example
    -------
    condition: 2*y - 5 == 7*x + 2
    master0 = 4
    
    return -> lambda y: 2*y - 35
    
    """
    
    if '=' in condition and not '==' in condition:
        sep = '='
    elif '==' in condition:
        sep = '=='
        
    lhs = condition.split(sep)[0]
    rhs = condition.split(sep)[1]
    f1 = f'{lhs} - ({rhs})'
    
    if not 'z' in condition:
        f1 = f1.replace('y', f'{slave0}')
        func = lambda x: eval(f1)
    else:
        f1 = f1.replace('z', f'{slave0}')
        func = lambda y: eval(f1)
    
    return func

def main():
    
    condition = '2*y - 5 == 7*z + 2'
    slave0 = 4
    f = condition_2_func(condition, slave0)
    
    y = optimize.newton(f, x0 = 0)
    
    print(y)
    
if __name__ == '__main__':
    main()
    
    
        