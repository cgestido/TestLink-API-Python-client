# ! /usr/bin/python
# -*- coding: UTF-8 -*-

#  Copyright 2011-2017 Luiko Czub, Olivier Renault, James Stock, TestLink-API-Python-client developers
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file_contents except in compliance with the License.
#  You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#
# ------------------------------------------------------------------------

# import xmlrpclib

from __future__ import print_function
from .testlinkapigeneric import TestlinkAPIGeneric, TestLinkHelper
from .testlinkerrors import TLArgError
import sys
import re
import ast


class TestlinkAPIClient(TestlinkAPIGeneric):
	""" client for XML-RPC communication between Python and TestLink

		Inherits TestLink API methods from the generic client TestlinkAPIGeneric.

		Defines Service Methods like "countProjects" and change the
		configuration for positional and optional arguments in a way, that often
		used arguments are positional.
		- see _changePositionalArgConfig()
		- configuration of positional arguments is consistent with v0.4.0

		Changes on Service Methods like "countProjects" should be implemented in
		this class or sub classes
		Changes of TestLink API methods should be implemented in generic API
		TestlinkAPIGeneric.
	"""

	__slots__ = ['stepsList']
	__author__ = 'Luiko Czub, Olivier Renault, James Stock, TestLink-API-Python-client developers'

	def __init__(self, server_url, devKey, **kwargs):
		""" call super for init generell slots, init sepcial slots for teststeps
			and define special positional arg settings """

		kwargs['allow_none'] = True
		super(TestlinkAPIClient, self).__init__(server_url, devKey, **kwargs)
		# allow_none is an argument from xmlrpclib.Server()
		# with set to True, it is possible to set positional args to None, so
		# alternative optional arguments could be set
		# example - testcaseid is set :
		# reportTCResult(None, newTestPlanID, None, 'f', '', guess=True,
		#                             testcaseexternalid=tc_aa_full_ext_id)
		# otherwise xmlrpclib raise an error, that None values are not allowed
		self.stepsList = []
		self._changePositionalArgConfig()

	def _changePositionalArgConfig(self):
		""" set special positional arg configuration, which differs from the
			generic configuration """
		pos_arg_config = self._positionalArgNames

		# createTestCases sets argument 'steps' with values from .stepsList
		# - user must not passed a separate stepList
		pos_arg_config['createTestCase'] = ['testcasename', 'testsuiteid',
											'testprojectid', 'authorlogin', 'summary']  # , 'steps']
		# getTestCase
		pos_arg_config['getTestCase'] = ['testcaseid']
		# createVuild
		pos_arg_config['createBuild'] = ['testplanid', 'buildname', 'buildnotes']
		# reportTCResult
		pos_arg_config['reportTCResult'] = ['testcaseid', 'testplanid',
											'buildname', 'status', 'notes']
		# uploadExecutionAttachment
		pos_arg_config['uploadExecutionAttachment'] = ['executionid', 'title',
													   'description']
		# getTestCasesForTestSuite
		pos_arg_config['getTestCasesForTestSuite'] = ['testsuiteid', 'deep',
													  'details']
		# getLastExecutionResult
		pos_arg_config['getLastExecutionResult'] = ['testplanid', 'testcaseid']
		# getTestCaseCustomFieldDesignValue
		pos_arg_config['getTestCaseCustomFieldDesignValue'] = [
			'testcaseexternalid', 'version', 'testprojectid',
			'customfieldname', 'details']
		# getTestCaseAttachments
		pos_arg_config['getTestCaseAttachments'] = ['testcaseid']

	#
	#  BUILT-IN API CALLS - extented / customised against generic behaviour
	#

	def echo(self, message):
		return self.repeat(message)

	def getTestCaseIDByName(self, *argsPositional, **argsOptional):
		""" getTestCaseIDByName : Find a test case by its name
		positional args: testcasename,
		optional args : testsuitename, testprojectname, testcasepathname

		testcasepathname : Full test case path name,
				starts with test project name , pieces separator -> ::

		server return can be a list or a dictionary
		- optional arg testprojectname seems to create a dictionary response

		this methods customize the generic behaviour and converts a dictionary
		response into a list, so methods return will be always a list """

		response = super(TestlinkAPIClient, self).getTestCaseIDByName(
			*argsPositional, **argsOptional)
		if type(response) == dict:
			# convert dict into list - just use dicts values
			response = list(response.values())
		return response

	def createTestCase(self, *argsPositional, **argsOptional):
		""" createTestCase: Create a test case
		positional args: testcasename, testsuiteid, testprojectid, authorlogin,
						 summary
		optional args : steps, preconditions, importance, executiontype, order,
						internalid, checkduplicatedname, actiononduplicatedname,
						status, estimatedexecduration

		argument 'steps' will be set with values from .stepsList,
		- when argsOptional does not include a 'steps' item
		- .stepsList can be filled before call via .initStep() and .appendStep()

		otherwise, optional arg 'steps' must be defined as a list with
		dictionaries , example
			[{'step_number' : 1, 'actions' : "action A" ,
				'expected_results' : "result A", 'execution_type' : 0},
				 {'step_number' : 2, 'actions' : "action B" ,
				'expected_results' : "result B", 'execution_type' : 1},
				 {'step_number' : 3, 'actions' : "action C" ,
				'expected_results' : "result C", 'execution_type' : 0}]

		"""

		# store current stepsList as argument 'steps', when argsOptional defines
		# no own 'steps' item
		if self.stepsList:
			if 'steps' in argsOptional:
				raise TLArgError('confusing createTestCase arguments - ' +
								 '.stepsList and method args define steps')
			argsOptional['steps'] = self.stepsList
			self.stepsList = []
		return super(TestlinkAPIClient, self).createTestCase(*argsPositional,
															 **argsOptional)

	#
	#  ADDITIONNAL FUNCTIONS- copy test cases
	#

	def getProjectIDByNode(self, a_nodeid):
		""" returns project id , the nodeid belongs to."""

		# get node path
		node_path = self.getFullPath(int(a_nodeid))[a_nodeid]
		# get project and id
		a_project = self.getTestProjectByName(node_path[0])
		return a_project['id']

	def copyTCnewVersion(self, origTestCaseId, origVersion=None, **changedAttributes):
		""" creates a new version for test case ORIGTESTCASEID

		ORIGVERSION specifies the test case version, which should be copied,
					default is the max version number

		if the new version should differ from the original test case, changed
		api arguments could be defined as key value pairs.
		Example for changed summary and importance:
		-  copyTCnewVersion('4711', summary = 'The summary has changed',
									importance = '1')
		Remarks for some special keys:
		'steps': must be a complete list of all steps, changed and unchanged steps
				 Maybe its better to change the steps in a separat call using
				 createTestCaseSteps with action='update'.
		"""

		return self._copyTC(origTestCaseId, changedAttributes, origVersion,
							duplicateaction='create_new_version')

	def copyTCnewTestCase(self, origTestCaseId, origVersion=None, **changedAttributes):
		""" creates a test case with values from test case ORIGTESTCASEID

		ORIGVERSION specifies the test case version, which should be copied,
					default is the max version number

		if the new test case should differ from the original test case, changed
		api arguments could be defined as key value pairs.
		Example for changed test suite and importance:
		-  copyTCnewTestCaseVersion('4711', testsuiteid = '1007',
											importance = '1')

		Remarks for some special keys:
		'testsuiteid': defines, in which test suite the TC-copy is inserted.
				 Default is the same test suite as the original test case.
		'steps': must be a complete list of all steps, changed and unchanged steps
				 Maybe its better to change the steps in a separat call using
				 createTestCaseSteps with action='update'.

		"""

		return self._copyTC(origTestCaseId, changedAttributes, origVersion,
							duplicateaction='generate_new')

	def _copyTC(self, origTestCaseId, changedArgs, origVersion=None, **options):
		""" creates a copy of test case with id ORIGTESTCASEID

		returns createTestCase response for the copy

		CHANGEDARGUMENTS defines a dictionary with api arguments, expected from
				 createTestCase. Only arguments, which differ between TC-orig
				 and TC-copy must be defined
		Remarks for some special keys:
		'testsuiteid': defines, in which test suite the TC-copy is inserted.
				 Default is the same test suite as the original test case.
		'steps': must be a complete list of all steps, changed and unchanged steps
				 Maybe its better to change the steps in a separat call using
				 createTestCaseSteps with action='update'.

		ORIGVERSION specifies the test case version, which should be copied,
					default is the max version number

		OPTIONS are optional key value pairs to influence the copy process
		- details see comments _copyTCbuildArgs()

		"""

		# get orig test case content
		origArgItems = self.getTestCase(origTestCaseId, version=origVersion)[0]
		# get orig test case project id
		origArgItems['testprojectid'] = self.getProjectIDByNode(origTestCaseId)

		# build args for the TC-copy
		(posArgValues, newArgItems) = self._copyTCbuildArgs(origArgItems,
															changedArgs, options)
		# create the TC-Copy
		response = self.createTestCase(*posArgValues, **newArgItems)
		return response

	def _copyTCbuildArgs(self, origArgItems, changedArgs, options):
		"""  build Args to create a new test case .
		ORIGARGITEMS is a dictionary with getTestCase response of an existing
					 test case
		CHANGEDARGS is a dictionary with api argument for createTestCase, which
					 should differ from these
		OPTIONS is a dictionary with settings for the copy process

		'duplicateaction': decides, how the TC-copy is inserted
		   - 'generate_new' (default): a separate new test case is created, even
				 if name and test suite are equal
		   - 'create_new_version': if the target test suite includes already a
				 test case with the same name, a new version is created.
				 if the target test suite includes not a test case with the
				 defined name, a new test case with version 1 is created
		"""

		# collect info, which arguments createTestCase expects
		(posArgNames, optArgNames, manArgNames) = \
			self._apiMethodArgNames('createTestCase')
		# some argNames not realy needed
		optArgNames.remove('internalid')
		optArgNames.remove('devKey')

		# mapping between getTestCase response and createTestCase arg names
		externalArgNames = posArgNames[:]
		externalArgNames.extend(optArgNames)
		externalTointernalNames = {'testcasename': 'name',
								   'testsuiteid': 'testsuite_id', 'authorlogin': 'author_login',
								   'executiontype': 'execution_type', 'order': 'node_order',
								   'estimatedexecduration': 'estimated_exec_duration'}

		# extend origItems with some values needed in createTestCase
		origArgItems['checkduplicatedname'] = 1
		origArgItems['actiononduplicatedname'] = options.get('duplicateaction',
															 'generate_new')
		# build arg dictionary for TC-copy with orig values
		newArgItems = {}
		for exArgName in externalArgNames:
			inArgName = externalTointernalNames.get(exArgName, exArgName)
			newArgItems[exArgName] = origArgItems[inArgName]

		# if changed values defines a different test suite, add the correct
		# project id
		if 'testsuiteid' in changedArgs:
			changedProjID = self.getProjectIDByNode(changedArgs['testsuiteid'])
			changedArgs['testprojectid'] = changedProjID

		# change orig values for TC-copy
		for (argName, argValue) in list(changedArgs.items()):
			newArgItems[argName] = argValue

		# separate positional and optional createTestCase arguments
		posArgValues = []
		for argName in posArgNames:
			posArgValues.append(newArgItems[argName])
			newArgItems.pop(argName)

		return (posArgValues, newArgItems)

	#
	#  ADDITIONNAL FUNCTIONS- keywords
	#

	def listKeywordsForTC(self, internal_or_external_tc_id):
		""" Returns list with keyword for a test case
		INTERNAL_OR_EXTERNAL_TC_ID defines
		- either the internal test case ID (8111 or '8111')
		- or the full external test case ID ('NPROAPI-2')

		Attention:
		- the tcversion_id is not supported
		- it is not possible to ask for a special test case version, cause TL
		  links keywords against a test case and not a test case version
		"""

		# ToDo LC 12.01.15 - simplify code with TL 1.9.13 api getTestCaseKeywords
		# - indirect search via test suite and getTestCasesForTestSuite() isn't
		#   necessary any more
		# - see enhancement issue #45

		a_tc_id = str(internal_or_external_tc_id)

		if '-' in a_tc_id:
			# full external ID like 'NPROAPI-2', but we need the internal
			a_tc = self.getTestCase(None, testcaseexternalid=a_tc_id)[0]
			a_tc_id = a_tc['testcase_id']

		# getTestCaseKeywords  returns a dictionary like
		#   {'12622': {'34': 'KeyWord01', '36': 'KeyWord03'}}
		# key is the testcaseid, why that? cause it is possible to ask for
		# a set of test cases.  we are just interested in one tc
		a_keyword_dic = self.getTestCaseKeywords(testcaseid=a_tc_id)[a_tc_id]
		keywords = a_keyword_dic.values()

		return list(keywords)

	def listKeywordsForTS(self, internal_ts_id):
		""" Returns dictionary with keyword lists for all test cases of
			test suite with id == INTERNAL_TS_ID
		"""

		a_ts_id = str(internal_ts_id)
		all_tc_for_ts = self.getTestCasesForTestSuite(a_ts_id, False,
													  'full', getkeywords=True)
		response = {}
		for a_ts_tc in all_tc_for_ts:
			tc_id = a_ts_tc['id']
			keyword_details = a_ts_tc.get('keywords', {})
			if sys.version_info[0] < 3:
				keywords = map((lambda x: x['keyword']), keyword_details.values())
			else:
				keywords = [kw['keyword'] for kw in keyword_details.values()]
			response[tc_id] = keywords

		return response

	#
	#  ADDITIONNAL FUNCTIONS
	#

	def countProjects(self):
		""" countProjects :
		Count all the test project
		"""
		projects = self.getProjects()
		return len(projects)

	def countTestPlans(self):
		""" countProjects :
		Count all the test plans
		"""
		projects = self.getProjects()
		nbTP = 0
		for project in projects:
			ret = self.getProjectTestPlans(project['id'])
			nbTP += len(ret)
		return nbTP

	def countTestSuites(self):
		""" countProjects :
		Count all the test suites
		"""
		projects = self.getProjects()
		nbTS = 0
		for project in projects:
			TestPlans = self.getProjectTestPlans(project['id'])
			for TestPlan in TestPlans:
				TestSuites = self.getTestSuitesForTestPlan(TestPlan['id'])
				nbTS += len(TestSuites)
		return nbTS

	def countTestCasesTP(self):
		""" countProjects :
		Count all the test cases linked to a Test Plan
		"""
		projects = self.getProjects()
		nbTC = 0
		for project in projects:
			TestPlans = self.getProjectTestPlans(project['id'])
			for TestPlan in TestPlans:
				TestCases = self.getTestCasesForTestPlan(TestPlan['id'])
				nbTC += len(TestCases)
		return nbTC

	def countTestCasesTS(self):
		""" countProjects :
		Count all the test cases linked to a Test Suite
		"""
		projects = self.getProjects()
		nbTC = 0
		for project in projects:
			TestPlans = self.getProjectTestPlans(project['id'])
			for TestPlan in TestPlans:
				TestSuites = self.getTestSuitesForTestPlan(TestPlan['id'])
				for TestSuite in TestSuites:
					TestCases = self.getTestCasesForTestSuite(
						TestSuite['id'], 'true', 'full')
					for TestCase in TestCases:
						nbTC += len(TestCases)
		return nbTC

	def countPlatforms(self):
		""" countPlatforms :
		Count all the Platforms in TestPlans
		"""
		projects = self.getProjects()
		nbPlatforms = 0
		for project in projects:
			TestPlans = self.getProjectTestPlans(project['id'])
			for TestPlan in TestPlans:
				Platforms = self.getTestPlanPlatforms(TestPlan['id'])
				nbPlatforms += len(Platforms)
		return nbPlatforms

	def countBuilds(self):
		""" countBuilds :
		Count all the Builds
		"""
		projects = self.getProjects()
		nbBuilds = 0
		for project in projects:
			TestPlans = self.getProjectTestPlans(project['id'])
			for TestPlan in TestPlans:
				Builds = self.getBuildsForTestPlan(TestPlan['id'])
				nbBuilds += len(Builds)
		return nbBuilds

	def listProjects(self):
		""" listProjects :
		Lists the Projects (display Name & ID)
		"""
		projects = self.getProjects()
		for project in projects:
			print("Name: %s ID: %s " % (project['name'], project['id']))

	def initStep(self, actions, expected_results, execution_type):
		""" initStep :
		Initializes the list which stores the Steps of a Test Case to create
		"""
		self.stepsList = []
		lst = {}
		lst['step_number'] = '1'
		lst['actions'] = actions
		lst['expected_results'] = expected_results
		lst['execution_type'] = str(execution_type)
		self.stepsList.append(lst)
		return True

	def appendStep(self, actions, expected_results, execution_type):
		""" appendStep :
		Appends a step to the steps list
		"""
		lst = {}
		lst['step_number'] = str(len(self.stepsList) + 1)
		lst['actions'] = actions
		lst['expected_results'] = expected_results
		lst['execution_type'] = str(execution_type)
		self.stepsList.append(lst)
		return True

	def getProjectIDByName(self, projectName):
		projects = self.getProjects()
		result = -1
		for project in projects:
			if (project['name'] == projectName):
				result = project['id']
				break
		return result

	def bulkTestCaseUpload(self, login, file_contents, testfile_class):
		testSuite = self._parseFileToObject(testfile_class.set_tree_path, file_contents)
		testSuite['project_id'] = self.getProjectIDByName(testSuite['project_name'])
		if testSuite['project_id'] is -1:
			print("Error: #{testSuite['project_name']} entered does not exist in TestLink.")
		testSuite['id'] = self.getOrCreateTestSuite(testSuite['project_id'], testSuite)
		remoteHostTestCases = self.getTestCasesForTestSuite(testSuite['id'], 'true', 'simple')
		# Iterate through the testcases add them to TestLink if needed
		i = 0
		for testCase in testSuite['testCases']:
			# Search external list for the test case, if it isn't there add it
			# If the case does not exist add it.
			if len(filter(lambda case: case['name'] == testCase['name'], remoteHostTestCases)) == 0:
				posArgValues = [testCase['name'], testSuite['id'], testSuite['project_id'], login,
								'Test from Test/Unit TestCases']
				optArgValues = {'steps': testCase['steps']}
				response = self.createTestCase(*posArgValues, **optArgValues)

				# Upload additional parameters if they are
				if testfile_class.testlink_params:
					postArgValues = [
						testfile_class.testlink_params['project_prefix'] + response[0]['additionalInfo']['external_id'], 1, 1,
						{"Automation Type": testfile_class.testlink_params['automation_type']}]
					if 'jira_story' in testfile_class.testlink_params:
						postArgValues[3]['JIRA Story'] = testfile_class.testlink_params['jira_story']
					self.updateTestCaseCustomFieldDesignValue(*postArgValues)
					if 'keywords' in testfile_class.testlink_params:
						self.addTestCaseKeywords(
							{testfile_class.testlink_params['project_prefix'] + response[0]['additionalInfo']['external_id']:
								 testfile_class.testlink_params['keywords']})
				i += 1
		if i == 0:
			print('There were no test cases to upload' + '\nBulk Test Upload Complete')
		else:
			print('[' + str(i) + ']' + ' Test Cases Created in TestLink' + '\nBulk Test Upload Complete')

	def _parseFileToObject(self, tree_path, path):
		file_contents = open(path, 'r').read()
		testSuite = {}
		testSuite['tree_path'] = tree_path
		testSuite['project_name'] = testSuite['tree_path'][0]
		testSuite['tree_path'].pop(0)
		# Delete the project_name form the tree path since it isn't a top_level_folder
		testSuite['ClassData'] = (re.search("(#.*\n?)+\nclass\s*\w*", file_contents).group(0).split('class '))
		testSuite['Summary'] = testSuite['ClassData'][0].lstrip().replace('#', '').replace('\n', '')
		testSuite['Name'] = re.search('class \w+', file_contents).group(0).split(" ")[1]
		testcaseStrings = re.findall("((((# .*)\n)\t?(....)?)+(#\n\t?(....)?)(((# .*)\n\t?)(....)?)+(def test(_\w*)))", file_contents)
		testSuite['testCases'] = []
		for testCase in testcaseStrings:
			case = {}
			temp = re.split('(#\n\t?(....)?)', testCase[0])
			temp1 = re.split(r'(def test(_\w*))', temp[3])
			name = temp1[1].replace('def ', '').replace('\n', '')
			actions = re.sub(r'\s+', ' ', temp[0].replace('# ', '').replace('\n', '').replace('#', ''))
			expected = re.sub(r'\s+', ' ', temp1[0].replace('Expected: ', '').replace('#', '').replace('\n', ''))
			case['steps'] = [{'step_number': 1, 'actions': actions, 'expected_results': expected, 'execution_type': 2}]
			case['name'] = name
			testSuite['testCases'].append(case)
		return testSuite


	def getOrCreateTestSuite(self, project_id, testSuite):
		# Get the Suite ID's etc for each Test Suite Folder in the path
		self._expandTreePath(project_id, testSuite)
		# Get all the test suites (test files) in the lowest folder
		parent = self.getTestSuitesForTestSuite(int(testSuite['tree_path'][-1]['id']))
		# If there are none, add the test file_contents
		if not parent:
			return self._createTestCase(testSuite, project_id)
		# In cases where one test suite exists, a dictionary is returned from testlinkapi
		elif 'parent_id' in parent: ##  bool(type(parent).__name__ == 'dict')
			return parent['id']
		# Case when there are multiple test suites returned from testlink
		else:
			result = filter(lambda suite: suite['name'] == testSuite['Name'], parent.values())
			if len(result) == 0:
				return self._createTestCase(testSuite, project_id)
			else:
				return result[0]['id']


	def _createTestCase(self, testSuite, project_id):
		posArgValues = [project_id, testSuite['Name'], testSuite['Summary']]
		optArgValues = {'parentid': testSuite['tree_path'][-1]['id']}
		result = self.createTestSuite(*posArgValues, **optArgValues)[0]
		return result['id']


	def _expandTreePath(self, project_id, testSuite):
		i = 0
		for folder in testSuite['tree_path']:
			if i == 0:
				top_level_suites = self.getFirstLevelTestSuitesForTestProject(project_id)
				if not top_level_suites:
					print(testSuite['project_name'] + ' does not have any Test Suites.' +
						  '\nPlease add the first level of Test Suites')
					sys.exit()
				testSuite['tree_path'][i] = filter(lambda suite: suite['name'] == folder, top_level_suites)[0]
			else:
				parent = self.getTestSuitesForTestSuite(testSuite['tree_path'][i - 1]['id'])
				# First level test suite, the parent is always the project_id
				# In the case that testlink returns a single dict. This is the case where one folder exists
				if 'id' in parent:
					testSuite['tree_path'][i] = parent
				# Handles the case when the API returns multiple results (Folder doesn't exist and multiple responses)
				else:
					result = filter(lambda suite: suite['name'] == folder, parent.values())
					# The response value will be zero if there is not a match. Add the folder to TestLink
					if len(result) == 0:
						print('Unable to find folder in TestLink. Creating New Folder ' + folder +
							  ' under parent folder ' + testSuite['tree_path'][i - 1]['name'])
						posArgValues = [project_id, folder, 'Created via TestLink Uploader']
						optArgValues = {'parentid': testSuite['tree_path'][i - 1]['id']}
						testSuite['tree_path'][i] = self.createTestSuite(*posArgValues, **optArgValues)[0]
						# since testlink doesnt return name - reset it
						testSuite['tree_path'][i]['name'] = folder
						if testSuite['tree_path'][i]['message'] == 'ok':
							print('Created Test Suite ID ' + testSuite['tree_path'][i]['id'] + ' Name ' +
								  testSuite['tree_path'][i]['name'])
						else:
							print('Unable to create the Test Suite: ' + testSuite['tree_path'][i]['message'])
					else:
						testSuite['tree_path'][i] = filter(lambda suite: suite['name'] == folder, parent.values())[0]
			i += 1


if __name__ == "__main__":
	tl_helper = TestLinkHelper()
	tl_helper.setParamsFromArgs()
	myTestLink = tl_helper.connect(TestlinkAPIClient)
	print(myTestLink)
