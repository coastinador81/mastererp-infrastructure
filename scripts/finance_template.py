"""Project the Finance functional YAML onto its existing backend stack owner."""
import copy
import re


def backend_template(source):
    result=copy.deepcopy(source)
    manifest=source.get('Metadata',{}).get('FinanceFrontendComposition')
    if not manifest:raise ValueError('Explicit frontend composition manifest required')
    for section in ('Resources','Outputs'):
        owned=set(manifest[section])
        if not owned<=set(source.get(section,{})):raise ValueError('Incomplete ownership manifest')
        result[section]={key:value for key,value in source.get(section,{}).items() if key not in owned}
    if set(result['Resources'])!={'Administration'}:
        raise ValueError('Unexpected Finance backend owner; review before deploying')
    parameters=set();conditions=set()
    def inspect(node):
        if isinstance(node,list):
            for value in node:inspect(value)
        elif isinstance(node,dict):
            for key,value in node.items():
                if key=='Ref' and isinstance(value,str):parameters.add(value)
                elif key=='Condition' and isinstance(value,str):conditions.add(value)
                elif key=='Fn::If' and isinstance(value,list):conditions.add(value[0])
                elif key=='Fn::Sub':
                    expression=value if isinstance(value,str) else value[0]
                    parameters.update(re.findall(r'\$\{([A-Za-z0-9]+)\}',expression))
                inspect(value)
    inspect(result['Resources']);inspect(result.get('Outputs',{}))
    previous=set()
    while conditions!=previous:
        previous=set(conditions)
        for name in previous:
            if name not in source.get('Conditions',{}):raise ValueError('Missing backend condition')
            inspect(source['Conditions'][name])
    result['Parameters']={key:value for key,value in source['Parameters'].items() if key in parameters}
    if conditions:result['Conditions']={key:source['Conditions'][key] for key in conditions}
    else:result.pop('Conditions',None)
    metadata=result.get('Metadata',{});metadata.pop('FinanceFrontendComposition',None)
    if not metadata:result.pop('Metadata',None)
    return result
