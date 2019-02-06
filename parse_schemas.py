#/usr/bin/python3
#~/anaconda3/bin/python

from asnake.client import ASnakeClient
import json, requests, time, csv, traceback, re, sys, logging
import pprint

def error_log(filepath=None):
    if sys.platform == "win32":
        if filepath == None:
            logger = '\\Windows\\Temp\\error_log.log'
        else:
            logger = filepath
    else:
        if filepath == None:
            logger = '/tmp/error_log.log'
        else:
            logger = filepath
    logging.basicConfig(filename=logger, level=logging.DEBUG,
                        format='%(asctime)s %(levelname)s %(name)s %(message)s')
    return logger


class ASTemps():

    def __init__(self):
        self.client = ASnakeClient()
        self.auth = self.client.authorize()
        self.all_schemas = self.get_schemas()
        #a list of all enumerations
        #COULD ALSO DO /config/enumerations/names/:enum_name
        self.all_enums = self.get_dynamic_enums()
        #gets the list of schema names
        self.schema_list = [key for key in self.all_schemas.keys()]
        #gets the type list
        self.type_list = list(set([k for value in self.all_schemas.values() for k, v in value.items()]))
        self.jsonmodel_pattern = re.compile('(JSONModel)(\(:.*?\)\s)(uri|object|uri_or_object)')

    def get_schemas(self):
        schemas = self.client.get('/schemas').json()
        return(schemas)

    def get_schema(self, schema):
        schema = self.client.get('/schemas/' + schema).json()
        return(schema)

    def get_dynamic_enums(self):
        enums = self.client.get('/config/enumerations').json()
        return(enums)

    def parse_jsonmodel(self, obj_value):
        #reg ex to capture all jsonmodel references in schema
        #jsonmodel = re.compile('(JSONModel)(\(:.*?\)\s)(uri|object|uri_or_object)')
        logging.debug('starting jsonmodel')
        if self.jsonmodel_pattern.match(obj_value):
            logging.debug('match with ' + str(obj_value))
            #gets the name of the schema
            stripped_string = obj_value[obj_value.find("(")+1:obj_value.find(")")][1:]
            if stripped_string != 'repository':
                logging.debug('Getting schema for: ' + stripped_string)
                jsonmodel_schema = self.all_schemas[stripped_string]
            #wondering if this is where the problem is??? I know this works in some cases
                if 'uri' in obj_value:
                    logging.debug('uri in obj_value')
                    parsed_json = {'ref': jsonmodel_schema['uri']}
                    logging.debug(str(parsed_json))
                #LOL this also gets digital objects
                if 'object' in obj_value:
                    if 'digital_object' not in obj_value:
                        logging.debug('object in obj_value')
                    #workaround for testing - infinite recursion - but only fixes part of it...
                        if stripped_string == 'note_outline_level':
                            parsed_json = None
                        else:
                        #THIS IS BROKEN!!!! INFINITE RECURSION
                            logging.debug("obj_value " + str(obj_value))
                            logging.debug('running parse_schema on ' + str(obj_value) )
                            parsed_json = self.parse_schema(stripped_string, jsonmodel_schema)
            #saves lots of memory, likely will not change.
            if stripped_string == 'repository':
                parsed_json = {'ref': '/repositories/:repo_id'}
        return parsed_json

    #still more to do with the other ref properties
    def parse_refs(self, schema_name, obj_name, obj_value):
        logging.debug('starting parse_refs on ' + str(schema_name) + ' ' + str(obj_name))
        #go through the properties of the refs
        if 'properties' in obj_value:
            logging.debug('properties in ' + str(obj_value))
            if 'ref' in obj_value['properties']:
                logging.debug('ref in properties')
                if type(obj_value['properties']['ref']['type']) is list:
                    logging.debug('Type of ref is list')
                    logging.debug("obj_value['properties']['ref']['type']: " +  str(obj_value['properties']['ref']['type']))
                    ref_list = []
                    for ref in obj_value['properties']['ref']['type']:
                        logging.debug('Looping through ref list')
                        logging.debug(obj_value['properties']['ref']['type'])
                        logging.debug(ref['type'])
                        #FIX THIS
                        parsed_ref = self.parse_jsonmodel(ref['type'])
                        logging.debug('parsed ref ' + str(parsed_ref))
                        ref_list.append(parsed_ref)
                    logging.debug('ref_list: ' + str(ref_list))
                    return ref_list
                else:
                    logging.debug('Type of ref is not list')
                    if self.jsonmodel_pattern.match(obj_value['properties']['ref']['type']):
                        logging.debug('RE match ' + str(obj_value['properties']['ref']['type']))
                        logging.debug('calling parse_jsonmodel')
                        parsed_ref = self.parse_jsonmodel(obj_value['properties']['ref']['type'])
                        return parsed_ref
        else:
            logging.debug('properties not in ' + str(obj_name) + 'value dictionary')
            logging.debug(str(obj_value['ref']['type']))
            if self.jsonmodel_pattern.match(obj_value['ref']['type']):
                logging.debug(str(obj_value['ref']['type']) + ' matches jsonmodel pattern')
                logging.debug('Calling parse_jsonmodel on ' + str(obj_value['ref']['type']))
                parsed_ref = self.parse_jsonmodel(obj_value['ref']['type'])
                return parsed_ref


    def parse_enums(self, enum_name):
        enum_list = []
        for enum in self.all_enums:
            if enum['name'] == enum_name:
                for ev in enum['enumeration_values']:
                    enum_list.append(ev['value'])
        return enum_list


    def parse_schema(self, schema_name, schema_def):
        try:
            logging.debug("Working on schema: " + str(schema_name))
            template_dict = {}
            #Fixes infinite recursion for now
            exclusions = ['collection_management', 'rights_statement',  'rights_statement_act', 'note_rights_statement',
                            'note_rights_statement_act', 'children', 'deaccessions', '_inherited', 'rights_statements',
                            'external_id']
            for prop_name, prop_value in schema_def['properties'].items():
                logging.debug("Working on prop: " + str(prop_name))
                if schema_name in exclusions:
                    print(schema_name + ' in exclusion list')
                    continue
                elif prop_name in exclusions:
                    print(str(prop_name) + ' in exclusion list')
                    continue
                #If there is more than one type it will be stored in a list.
                elif type(prop_value['type']) is list:
                    '''
                    INTEGER/STRING

                    This is always (and only? )the lock version. Don't need to do anything
                    with it, but will keep in the check in case the schema changes.

                    '''
                    #WHAT WOULD HAPPEN IF I JUST SKIPPED ALTOGETHER - NOTHING STILL FUCKED!!
                    # if prop_value['type'] == ['integer', 'string']:
                    #     if prop_name == 'lock_version':
                    #         logging.debug(schema_name, prop_name, prop_value)
                    #         continue
                    #     if prop_name != 'lock_version':
                    #         template_dict[prop_name] = None
                    '''
                    What is this doing???

                    '''
                    if 'query' in prop_value['type'][0]:
                        continue
                        #logging.debug(schema_name, prop_name, prop_value)
                    '''
                    What is this doing???

                    '''
                    if type(prop_value['type'][0]) is dict:
                        continue
                        #if 'agent' in prop_value['type'][0]['type']:
                            #logging.debug(schema_name, prop_name, prop_value)
                #If there is only one type it won't be in a list.
                else:
                    '''
                    JSONMODEL TYPES

                    Can be either an object or URI. Refers to another schema or a reference
                    to another object. i.e. date subrecords, location URIs

                    '''
                    if self.jsonmodel_pattern.match(prop_value['type']):
                        logging.debug('Regex match, ' + str(prop_value['type']))
                        #Don't add read-only fields to the template. Might want to change this
                        #in the case of URIs or IDs...but don't worry about it for now.
                        if 'readonly' in prop_value:
                            logging.debug('Property value is readonly')
                            if 'subtype' in prop_value:
                                logging.debug('Subtype in property value')
                                if prop_value['subtype'] == 'ref':
                                    logging.debug('Subtype of ' + str(prop_name) + 'is ref, calling parse_jsonmodel on ' + str(prop_value['tyoe']))
                                    template_dict[prop_name] = self.parse_jsonmodel(prop_value['type'])
                        else:
                            logging.debug('readonly not in property value dict, calling parse_jsonmodel on ' + str(prop_value['type']))
                            template_dict[prop_name] = self.parse_jsonmodel(prop_value['type'])
                    elif prop_value['type'] == 'array':
                        logging.debug('Prop value type is array')
                        #this will always be the case I think? Check
                        if 'items' in prop_value:
                            #no need to have readonly fields in template???
                                #if there is more than one type
                            if type(prop_value['items']['type']) is list:
                                logging.debug('Type of array items is list')
                                template_dict[prop_name] = []
                            #this might always be object??? check and see
                                for prop_type in prop_value['items']['type']:
                                    if self.jsonmodel_pattern.match(prop_type['type']):
                                        parsed_json = self.parse_jsonmodel(prop_type['type'])
                                        template_dict[prop_name].append(parsed_json)
                                    if prop_type['type'] is 'object':
                                        logging.debug(schema_name, prop_name, prop_value)
                                #If there is only one type...
                            else:
                                logging.debug('Type of array items is object')
                                if prop_value['items']['type'] is 'object':
                                    if 'subtype' in prop_value['items']:
                                        #these usually have properties
                                        if 'properties' in prop_value['items']:
                                            template_dict[prop_name] = self.parse_refs(schema_name, prop_name, prop_value)
                                    else:
                                        if 'properties' in prop_value['items']:
                                            logging.debug(schema_name, schema_name, prop_name, prop_value)
                                if prop_value['items']['type'] == 'string':
                                    if 'enum' in prop_value['items']:
                                        template_dict[prop_name] = prop_value['items']['enum']
                                #if it matches the object pattern
                                if self.jsonmodel_pattern.match(prop_value['items']['type']):
                                    logging.debug(prop_name)
                                    logging.debug(str(prop_value['items']['type']))
                                    parsed_json = self.parse_jsonmodel(prop_value['items']['type'])
                                    template_dict[prop_name] = [parsed_json]
                    #Changing this from 'is' to '==' causes infinite recursion. Interestingly changing it above causes many
                    #fields to be removed from the templates - 2 other instances of is/== 'object'
                    elif prop_value['type'] == 'object':
                        logging.debug('Prop value type is object')
                        if 'properties' in prop_value:
                            if 'subtype' in prop_value:
                                logging.debug('subtype in prop value, calling parse_refs on ' + str(schema_name) + ' ' + str(prop_name))
                                #these are all refs I think
                                template_dict[prop_name] = self.parse_refs(schema_name, prop_name, prop_value)
                            else:
                                logging.debug('subtype not in prop_value: ')
                                logging.debug(schema_name, prop_name, prop_value)
                    elif prop_value['type'] == 'string':
                        logging.debug('Prop value is string')
                        #enums are always strings
                        if 'readonly' not in prop_value:
                            logging.debug('readonly not in prop value dictionary')
                            if 'enum' in prop_value:
                                template_dict[prop_name] = prop_value['enum']
                            if 'dynamic_enum' in prop_value:
                                template_dict[prop_name] = self.parse_enums(prop_value['dynamic_enum'])
                            else:
                                template_dict[prop_name] = None

                    elif prop_value['type'] in ['integer', 'boolean', 'date', 'date-time', 'number']:
                        logging.debug('Prop value is type int, bool, date, date-time, number')
                        #make sure this is correct, as in not missing something that should be there
                        if 'readonly' not in prop_value:
                            logging.debug('readonly not in prop value dictionary')
                            template_dict[prop_name] = None
                    else:
                        logging.debug('Value not of a recognized type')
        except KeyError:
            logging.debug('KeyError: ' + schema_name + ' ' + prop_name)
        except Exception as exc:
            logging.debug('Error: ' + schema_name + ' ' + prop_name)
            logging.debug(traceback.format_exc())
        finally:
            template_dict['jsonmodel_type'] = schema_name
        return template_dict


    #QUESTION - SHOULD I CREATE LITTLE FUNCTIONS FOR EACH TYPE - i.e if whatever is 'object',
    #then do function stuff...might help with the nesting


    #want to go through each schema and create a sample dictionary template
    #need to be able to handle just one schema
    def parse_schemas(self, schemas):
        template_dict = {}
        for schema_name, schema_def in schemas.items():
            #check for a parent - but one that isn't "abstract" because those fields are the same
            #WHAT TO DO WITH THIS????
            # if 'parent' in schema_def:
            #     pass
            temp = self.parse_schema(schema_name, schema_def)
            template_dict[schema_name] = temp
        return template_dict

    def create_csv_template(self, jsontemplatedict):
        '''
        Goal is to create the JSON templates, and then convert those to CSV file that can
        be used to create either full finding aids/top level records, or to update subrecords
        in bulk
        '''
        fileob = open(jsontemplatedict['jsonmodel_type'] + '.csv', 'a', encoding='utf-8', newline='')
        csvout = csv.writer(fileob)
        subfield_list = []
        for key, value in jsontemplatedict.items():
            if type(value) is list:
                #should I just check the first one instead of looping through all?
                if type(value[0]) is dict:
                    for item in value:
                        for k in item.keys():
                            subfield_list.append(jsontemplatedict['jsonmodel_type'] + '_' + key + '_' + k)
                #only two options for lists, correct?
                if type(value[0]) is not dict:
                    #this means that it's just a list of enums probably - right?? No other list formats
                    #do I need the check now that I removed the loop?
                    check = jsontemplatedict['jsonmodel_type'] + '_' + key
                    if check not in subfield_list:
                        subfield_list.append(jsontemplatedict['jsonmodel_type'] + '_' + key)
            else:
                subfield_list.append(jsontemplatedict['jsonmodel_type'] + '_' + key)
        csvout.writerow(subfield_list)
        fileob.close()
        return subfield_list

    #Wrapper loop to create all templates
    def create_csv_templates(self, jsontemplates):
        for template_key, template_value in jsontemplates.items():
            self.create_csv_template(template_value)

    def download_templates(self, jsontemplates):
        for template_key, template_value in jsontemplates.items():
            outfile = open(str(template_key) + '.json', 'w', encoding='utf-8')
            json.dump(template_value, outfile, sort_keys = True, indent = 4)

def run():
    error_log('/Users/aliciadetelich/Dropbox/git/archivesspace_templates/log.log')
    t = ASTemps()
    all_schemas = t.all_schemas
    try:
        template_func = t.parse_schema('archival_object', all_schemas['archival_object'])
        pprint.pprint(template_func)
        # for schema_key, schema_value in all_schemas.items():
        #     print('SCHEMA: ' + str(schema_key))
        #     template_func = t.parse_schema(schema_key, schema_value)
        #     pprint.pprint(template_func)
    except:
        logging.debug('error')
    #return y

if __name__ == '__main__':
    p = run()

'''TO-DO:

Figure out notes = mostly done except for infinite recursion
SOME refs still not working

Getting some read only stuff = created by, last modified by, etc.
Do I want any of that in the template (i.e. URI) or no?

Note outline level causes infinite recursion - have workaround in place but need fix
Do I need repeated tests against readonly?
Missing anything?
Check if collection mgmt records can be created in a ao template, etc. - or should be removed...
Any way to combine some things into functions?
Have some overlapping ifs - check logging.debug statements
Test with latest version
Extra nones in output??

Automatically add a drop-down to a CSV (or Excel) file for enumerations
Deaccessions, collection management should not be added to template for resources, etc. - added to exclusions


Maybe look for readonlies that do NOT have subtypes; lock version is NOT read only, but is
the only integer/string
Also check for "is_missing" fields...
Check for '_inherited'
arcrole

Lock version still showing up - DONE
Enums not working right - DONE
Need to put subrecords into a list - DONE
Fix digital object in instance - puts the whole thing in there when prob just want the ref - DONE
'''
