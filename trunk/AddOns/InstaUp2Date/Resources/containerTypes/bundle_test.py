#!/usr/bin/python

import os, unittest

import bundle
from .container		import container

class folder_test(unittest.TestCase):
	
	def test_applicationsFolder(self):
		'''Test that the Mail.app folder is processed as a bundle'''
		
		thisItem = container('/Applications/Mail.app')
		
		self.assertEqual(thisItem.getContainerType(), 'bundle', 'Expected containerType for /Applications/Mail.app to be "bundle", but got: ' + thisItem.getContainerType())