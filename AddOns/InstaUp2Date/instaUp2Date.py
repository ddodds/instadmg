#!/usr/bin/python

# InstaUpToDate
#
#	This script parses one or more catalog files to fill in the 

import os, sys, re, getopt
import hashlib, urllib2, tempfile, shutil, subprocess
import Foundation, checksum
from datetime import date

#------------------------------SETTINGS------------------------------

svnRevision					= int('$Revision$'.split(" ")[1])
versionString				= "0.4b (svn revision: %i)" % svnRevision

relativePathToInstaDMG		= "../../" # the relative path between InstaUp2date and InstaDMG
relativePathFromInstaDMG	= "AddOns/InstaUp2Date/"
instaDMGName				= "instadmg.bash" # name of the InstaDMG executable

# this group needs to be relative to InstaDMG
appleUpdatesFolder			= "InstallerFiles/BaseUpdates"
customPKGFolder 			= "InstallerFiles/CustomPKG"
userSuppliedPKGFolder		= "InstallerFiles/InstaUp2DatePackages" # user-created packages

catalogFolderName			= "CatalogFiles"
catalogFileExension			= ".catalog"

cacheFolder					= "Caches/InstaUp2DateCache" # the location of the cache folder relative to the InstaDMG folder

READ_CHUNK_SIZE				= 1024; # how large a chunk to grab while checksumming. changing this can affect performance

baseOSSectionName			= "Base OS Disk"

allowedCatalogFileSettings	= [ "ISO Language Code", "Output Volume Name", "Output File Name", "Path to Scratch Space", "Path to Created ASR Image" ]

# these should be in the order they run in
systemSectionTypes			= [ "OS Updates", "System Settings" ]
addedSectionTypes			= [ "Apple Updates", "Third Party Software", "Third Party Settings", "Software Settings" ]


#--------------------------RUNTIME VARIABLES-------------------------


# these will be filled in by setup
catalogFolder				= None

def setup():
	#-----------------------CHANGE TO PROPER DIRECTORY-------------------
	
	# we have to cd to the proper directory (the one with InstaDMG in it)
	# by default the directory is two directories above the one containing the script
	
	os.chdir( os.path.join( os.path.dirname(sys.argv[0]), relativePathToInstaDMG ) ) # TODO: error handling
	
	if not(os.path.exists( instaDMGName )):
		# TODO: use mdfind to find InstaDMG
		raise Exception("Unable to locate InstaDMG") # TODO: improve error handling
	
	#-------------------------SETTINGS SANITY CHECK----------------------
	
	if not(os.path.exists(appleUpdatesFolder)) or not(os.path.isdir(appleUpdatesFolder)):
		raise Exception() # TODO: improve error handling
	
	if not(os.path.exists(customPKGFolder)) or not(os.path.isdir(customPKGFolder)):
		raise Exception() # TODO: improve error handling
	
	if not(os.path.exists(userSuppliedPKGFolder)) or not(os.path.isdir(userSuppliedPKGFolder)):
		raise Exception() # TODO: improve error handling
	
	global catalogFolder
	catalogFolder = os.path.join( relativePathFromInstaDMG, "CatalogFiles" )
	
	if not (os.path.exists(catalogFolder)) or not(os.path.isdir(catalogFolder)):
		raise Exception() # TODO: improve error handling
	
	if not(os.path.exists(cacheFolder)):
		# we will try to create this one if it does not exist
		if not(os.path.isdir(cacheFolder)):
			# something else there... bail
			raise Exception() # TODO: improve error handling
		os.makedirs(cacheFolder)
	if not(os.path.exists(cacheFolder)):
			raise Exception() # TODO: improve error handling
		
#---------------------------HELPER METHODS---------------------------

def usage (exitLevel=0):
	print "usage: \n\n There really should be more here" # TODO: create usage message
	sys.exit(exitLevel)

#-------------------------------CLASSES------------------------------

class instaUpToDate:
	"This is the central class that will manage the process. It should probably be a singleton object"
	
	global catalogFileExension
	
	#---------------------Class Variables-----------------------------
	
	sectionStartParser	= re.compile('^(?P<sectionName>[^\t]+):\s*(#.*)?$')
	packageLineParser	= re.compile('^\t(?P<prettyName>[^\t]*)\t(?P<archiveLocation>[^\t]+)\t(?P<archiveChecksum>\S+)(\t(?P<packageLocation>[^\t]+)\t(?P<packageChecksum>\S+))?\s*(#.*)?$')
	emptyLineParser		= re.compile('^\s*(?P<comment>#.*)?$')
	settingLineParser	= re.compile('^(?P<variableName>[^=]+) = (?P<variableValue>.*)')
	includeLineParser = re.compile('^\s*include-file:\s+(?P<location>.*)(\s*#.*)?$')
	
	catalogExtensionReplacer = re.compile( catalogFileExension + '$')
	
	suportedRemoteProtocols	= { "http":1, "https":1 }
	fileLocationParser  	= re.compile("^((?P<protocol>[^:]+)://(?P<server>[^/]+)/)?(?P<fullPath>(?P<path>.*?/)?(?P<fileName>[^/]*?(\.(?P<extension>[^\.]+?)?)))(?(1)\?(?P<queryString>.+))?$")
	
	#--------------------Instance Variables---------------------------

	packageGroups 			= {} # this will be init-ed in cleanInstaDMGFolders
	parsedFiles 			= {} # for loop checking
	
	# defaults
	outputVolumeNameDefault = "MacintoshHD"
	
	# things below this line will usually come from the first catalog file (top) that sets them
	catalogFileSettings		= {}
	
	topLevelCatalogFileName = None

	#------------------------Functions--------------------------------

	def parseFile(self, fileLocation, topLevel=False):
		
		global catalogFolder
		global catalogFileExension
		global allowedCatalogFileSettings
		
		# top-level catalog file need to do two things: clean out the InstaDMG folders, and set the outputFileName
		if topLevel == True:
			self.catalogFileSettings		= {}
			self.parsedFiles 				= {}
			self.cleanInstaDMGFolders()
			self.topLevelCatalogFileName	= self.catalogExtensionReplacer.sub( '', os.path.basename(fileLocation) )
					
		# the file passed could be an absolute path, a relative path, or a catalog file name
		#	the first two are handled without a special section, but the name needs some work
		
		if os.path.exists( os.path.join(catalogFolder, fileLocation) ):
			fileLocation = os.path.join(catalogFolder, fileLocation)
		elif os.path.exists( os.path.join(catalogFolder, fileLocation + catalogFileExension) ):
			fileLocation = os.path.join(catalogFolder, fileLocation + catalogFileExension)
	
		if self.parsedFiles.has_key(fileLocation):
			raise Exception('Loop detected in catalog files: %s' % fileLocation) # TODO: improve error handling
		self.parsedFiles[fileLocation] = 1
		
		fileLocationParsed = self.fileLocationParser.search( fileLocation )
		if fileLocationParsed == None:
			raise Exception('Unable to parse input file: %s' % fileLocation) # TODO: improve error handling
			
		if self.suportedRemoteProtocols.has_key( fileLocationParsed.group("protocol") ):
			# a web file that we need to process
			print "need to do something"
			
		elif fileLocationParsed.group("protocol") == None or fileLocationParsed.group("protocol").lower() == "file":
			# a local file refernce
		
			if fileLocationParsed.group("protocol") != None:
				# this is a file url, and we need to swizzle it into a regular file reference
				if fileLocationParsed.group("server"):
					fileLocation = os.path.join( fileLocationParsed.group("server"), fileLocationParsed.group("fullPath") )
				else:
					fileLocation = fileLocationParsed.group("fullPath")
					
			INPUTFILE = open(fileLocation, "r")
			
			
		else:
			# this is not a recognized file type
			raise Exception() # TODO: improve error handling
				
		if INPUTFILE == None:
				raise Exception('Unable to open input file: %s' % inputFilePath) # TODO: improve error handling
			
		currentSection = None;
		lineNumber = 0
		
		# parse through the file
		for line in INPUTFILE.readlines():
			lineNumber += 1
			
			if self.emptyLineParser.search(line):
				continue
			
			settingLineMatch = self.settingLineParser.search(line)
			if settingLineMatch:
				try:
					if allowedCatalogFileSettings.index( settingLineMatch.group("variableName") ):
						if not(self.catalogFileSettings.has_key( settingLineMatch.group("variableName") )):
							# Since it is not set, we can set it
							# TODO: log something if there is a conflict
							self.catalogFileSettings[settingLineMatch.group("variableName")] = settingLineMatch.group("variableValue")
				except:
					raise Exception('Unknown setting in catalog file: %s line number: %i\n%s' % (fileLocation, lineNumber, line)) # TODO: improve error handling
					
				continue
			
			includeLineMatch = self.includeLineParser.search(line)
			if includeLineMatch:
				self.parseFile( includeLineMatch.group("location") )
				continue
			
			sectionTitleMatch = self.sectionStartParser.search(line)
			if sectionTitleMatch:
				if not(sectionTitleMatch.group("sectionName")):
					raise Exception('Bad line in input file: %s line number: %i\n%s' % (fileLocation, lineNumber, line)) # TODO: improve error handling
							
				if not(self.packageGroups.has_key(sectionTitleMatch.group("sectionName"))) and sectionTitleMatch.group("sectionName") != baseOSSectionName:
					raise Exception('Unknown section title: %s on line: %i of file: %s\n%s' % (sectionTitleMatch.group("sectionName"), lineNumber, fileLocation, line) ) # TODO: improve error handling
				
				currentSection = sectionTitleMatch.group("sectionName")
				continue
				
			simpleLineMatch = self.packageLineParser.search(line)
			if simpleLineMatch:
				if currentSection == None:
					# we have to have a place to put this
					raise Exception() # TODO: improve error handling
					
				thisPackage = installerPackage( simpleLineMatch.group("prettyName"), simpleLineMatch.group("archiveLocation"), simpleLineMatch.group("archiveChecksum"), simpleLineMatch.group("packageLocation"), simpleLineMatch.group("packageChecksum") )
		
				thisPackage.printPackageInformation()
				
				self.packageGroups[currentSection].append(thisPackage)
				
				continue
				
			# if we got here, the line was not good
			raise Exception('Error in config file: %s line number: %i\n%s' % (fileLocation, lineNumber, line)) # TODO: improve error handling
			
		INPUTFILE.close()
		
	def arrangeFolders(self):
		"Create the folder structure in the InstaDMG areas, and pop in soft-links to the items in the cache folder"
	
		global appleUpdatesFolder
		global customPKGFolder 
		
		# TODO: combine these two into a loop
		
		groupings = [ [systemSectionTypes, appleUpdatesFolder], [addedSectionTypes, customPKGFolder] ]
		for sectionTypes, updateFolder in groupings:
			folderCounter = 1
			
			orderOfMagnitude = 1
			packageCounter = 0
			for thisSection in sectionTypes:
				packageCounter += len(self.packageGroups[thisSection])
				
			while packageCounter >= pow(10, orderOfMagnitude):
				orderOfMagnitude += 1
							
			for thisSection in sectionTypes:
				
				# there has got to be a better way of doing this
				
				for thisPackage in self.packageGroups[thisSection]:
					numberFormatString = '%0' + str(orderOfMagnitude) + 'd'
					newFolderPath = os.path.join(updateFolder, numberFormatString % folderCounter)
					
					if thisPackage.packageType == "folder":
						os.symlink( os.path.join("../..", thisPackage.packageCacheLocation), newFolderPath )
						# TODO: make this less dependent on the path
	
					elif thisPackage.archiveType == "dmg" and ( thisPackage.packageType == None or thisPackage.packageType == "dmg"):
						os.symlink( os.path.join("../..", thisPackage.packageCacheLocation), newFolderPath )
						# TODO: make this less dependent on the path
					
					else:
						os.mkdir(newFolderPath)
						os.symlink( os.path.join("../../..", thisPackage.packageCacheLocation), os.path.join(newFolderPath, thisPackage.packageFileName) )
						# TODO: make this less dependent on the path
						
					folderCounter = folderCounter + 1
				
		return True

	def cleanInstaDMGFolders(self):
		"This will go through and clean out the InstaDMG folders. It will choke on any real files in the hirarchy (it expects soft-links). It also cleans and sets-up instance variables for a new run."
		
		global appleUpdatesFolder
		global customPKGFolder
		global validSectionTypes
		
		# clean out the instance variables
		self.packageGroups = {}
		for group in systemSectionTypes + addedSectionTypes:
			self.packageGroups[group] = []
			
		parsedFiles = {}
		
		for instaDMGFolder in [appleUpdatesFolder, customPKGFolder]:
			for subFolder in os.listdir(instaDMGFolder):
				thisFolder = os.path.join(instaDMGFolder, subFolder)
				
				if re.match("\.", subFolder):
					continue
				
				if os.path.islink(thisFolder):
					os.remove(thisFolder)
					continue
				
				if not(os.path.isdir(thisFolder)):
					raise Exception("Not a folder: %s" % thisFolder) # TODO: improve error handling
				
				for thisItem in os.listdir(thisFolder):
					thisItemPath = os.path.join(thisFolder, thisItem)
					
					if not(os.path.islink(thisItemPath)) and not(re.match("\.DS_Store", thisItem)) and not(re.match("\.svn", thisItem)):
						raise Exception("Not a soft link: %s" % thisItemPath) # TODO: improve error handling
					
					if not(re.match("\.svn", thisItem)):
						os.remove(thisItemPath)
					
				os.rmdir(thisFolder)
	
	def runInstaDMG(self):
		global instaDMGName
	
		# defaults
		chosenLanguage			= "en"
		asrFileSystemNameOption	= []
		asrOutputFileNameOption	= []
		temporaryFolder			= []
		asrFolder				= []
		
		if self.catalogFileSettings.has_key("ISO Language Code"):
			chosenLanguage = self.catalogFileSettings["ISO Language Code"]
			# TODO: check with installer to see if it will accept this language code
			
		if self.catalogFileSettings.has_key("Output Volume Name"):
			asrFileSystemNameOption = ["-n", self.catalogFileSettings["Output Volume Name"]]
	
		if self.catalogFileSettings.has_key("Output File Name"):
			asrOutputFileNameOption = ["-m", self.catalogFileSettings["Output File Name"]]

		if self.catalogFileSettings.has_key("Path to Scratch Space"):
			temporaryFolder = ["-t", self.catalogFileSettings["Path to Scratch Space"]]

		if self.catalogFileSettings.has_key("Path to Created ASR Image"):
			asrFolder = ["-o", self.catalogFileSettings["Path to Created ASR Image"]]
		
		print "Running InstaDMG:\n\n"
		# we should be in the same directory as InstaDMG
		
		thisProcess = subprocess.Popen([os.path.join(os.getcwd(),instaDMGName), '-f'] + ["-i", chosenLanguage] + asrFileSystemNameOption + asrOutputFileNameOption + temporaryFolder + asrFolder)
		thisProcess.communicate()
		# TODO: a lot of improvements in handling of InstaDMG

class installerPackage:
	"This class represents a .pkg installer, and does much of the work."
		
	#---------------------Class Variables-----------------------------
		
	suportedRemoteProtocols	= { "http":1, "https":1 }
	
	checksumParser			= re.compile("^(?P<checksumType>[^:]+):(?P<checksum>\S+)")
	fileLocationParser  	= re.compile("^((?P<protocol>[^:]+)://(?P<server>[^/]+)/)?(?P<fullPath>(?P<path>.*?/)?(?P<fileName>[^/]*?(\.(?P<extension>[^\.]+?)?)?))(?(1)\?(?P<queryString>.+))?$")
	
	contentDispostionParser	= re.compile("^Content-Disposition:.*filename\s*=\s*\"(?P<filename>[^\"]+)\"", re.I)
	
	#--------------------Instance Variables---------------------------
	
	name					= None		# arbitrary text string for display	
	status					= "Needed"	# this can be "Needed", "Downloaded", "Verified", or "Invalid" - later: "Downloading" and "Verifying"
	statusMessage			= None		# for messages regarding the status - for later use
	sourceMessage			= None		# where the package was found
		
	archiveType				= None		# this can be "flatfilepkg", "zip", or "dmg"
	archiveLocation			= None		# can be a http(s): location or an absolute reference
	archiveChecksum			= None
	archiveChecksumType		= None
	archiveChecksumCorrect	= None		# once it has been checksummed this should be True or False
	
	packageType				= None		# this can be "flatfilepkg", "folder", "folderpkg", or "dmg"
	packageLocation			= None		# this should be the path to the .pkg inside a archive or a name that will be searched for in the archive directory
	packageFileName			= None		# the name of the .pkg file
	packageCacheLocation	= None		# the path to the package in the cache folder relative to the InstaDMG folder
	packageChecksum			= None
	packageChecksumType		= None
	packageChecksumCorrect	= None		# once it has been checksummed this should be True or False
	
	cacheFolderName			= None		# this is the location of the file in the cache
	instaDMGLocation		= None		# this is the relative location in the InstaDMG folder hierarchy
	
	#------------------------Functions--------------------------------
	
	def __init__(self, name, location, locationChecksumString, packageLocation = None, packageChecksumString = None):	
		self.name = name
		
		if location == None:
			# TODO: a bit better job of checking the location
			raise Exception(); # TODO: better errors
			
		if locationChecksumString == None:
			# TODO: a bit better job of checking the checksum format
			raise Exception(); # TODO: better errors
			
		if locationChecksumString == "?":
			locationChecksum = None;
			locationChecksumType = None;
		else:
			# if the checksum is a "?" that means the user does not want checksumming
			thisTemp = self.checksumParser.search(locationChecksumString)
			if thisTemp == None:
				raise Exception(); # TODO: better errors
			locationChecksum = thisTemp.group("checksum")
			locationChecksumType = thisTemp.group("checksumType")
		
			if locationChecksum == None:
				raise Exception(); # TODO: better errors
			if locationChecksumType == None:
				raise Exception(); # TODO: better errors
		
		# first we need to sort out the location... and package... information that we already have
		if packageLocation == None:
			# a local file, a remote flat-file pkg, a local folder, or a local dmg. We need to tell those cases apart
			
			# but first we can set the checksum information
			self.packageChecksum		= locationChecksum
			self.packageChecksumType	= locationChecksumType
			
			scannerResult = self.fileLocationParser.search(location)
						
			if scannerResult.group("protocol") == None or scannerResult.group("protocol").lower() == "file":
				# this means a local file of some sort
				
				# if this is a file:// url, then we might need to re-glue the <<server>> section on
				if scannerResult.group("protocol") and scannerResult.group("protocol").lower() == "file" and scannerResult.group("server"):
					thisFileLocation = os.path.join( scannerResult.group("server"), scannerResult.group("fullPath") )
				else:
					thisFileLocation = scannerResult.group("fullPath")
				
				if re.match(thisFileLocation, "/"): # absolute path, so this is the archive Location
					self.archiveLocation		= thisFileLocation
					self.archiveChecksum		= locationChecksum
					self.archiveChecksumType	= locationChecksumType
					
				# remote or not, is the file is a .pkg, then we have the file name
				if scannerResult.group("extension") and (scannerResult.group("extension").lower() == "pkg" or scannerResult.group("extension").lower() == "mpkg"):
					self.packageFileName = scannerResult.group("fileName")
					
				elif re.search( "/$", scannerResult.group("fullPath") ):
					# we have a folder
					self.packageFileName = scannerResult.group("fullPath")
					
				elif re.search( "\.dmg", scannerResult.group("fullPath"), re.I ):
					# this is a local dmg
					self.archiveLocation		= location
					self.archiveChecksum		= locationChecksum
					self.archiveChecksumType	= locationChecksumType
					
					self.packageFileName = scannerResult.group("fileName")
					
				else:
					if self.archiveLocation == None:
						# we have a non-pkg file as our package
						raise Exception(); # TODO: better errors

			elif self.suportedRemoteProtocols.has_key(scannerResult.group("protocol").lower()):
				# here we just need to slide the information into the archive section
				self.archiveLocation		= location
				self.archiveChecksum		= locationChecksum
				self.archiveChecksumType	= locationChecksumType
				
			else:
				# TODO: it would be good to be able to process ftp, afp, and smb locations
				# we don't know how to get to the file, so lets bail
				raise Exception(); # TODO: better errors
				
			self.packageLocation		= location
			
		else:
			# if they gave us all 4 items
						
			self.archiveLocation		= location
			self.archiveChecksum		= locationChecksum
			self.archiveChecksumType	= locationChecksumType
			
			scannerResult = self.fileLocationParser.search(packageLocation)
			if scannerResult.group("protocol") != None or scannerResult.group("fullPath") != scannerResult.group("fileName"):
				# note that we are not accepting file:// locations
				# and we are not accepting anything that is not a simple file name
				raise Exception(); # TODO: better errors
			self.packageFileName		= scannerResult.group("fileName")
			self.packageLocation		= scannerResult.group("fullPath")
			
			if packageChecksumString == None:
				raise Exception(); # TODO: better errors
				
			if packageChecksumString != "?":
				thisTemp = self.checksumParser.search(packageChecksumString)
				self.packageChecksum		= thisTemp.group("checksum")
				self.packageChecksumType	= thisTemp.group("checksumType")
		
		# if we don't have a package name, lets see if we can figure it out from the archive name
		if self.packageFileName == None:
			if self.archiveLocation != None:
				scannerResult = self.fileLocationParser.search(self.archiveLocation)
				if scannerResult == None: # it does not parse as a location
					raise Exception(); # TODO: better errors
					
				if self.suportedRemoteProtocols.has_key(scannerResult.group("protocol").lower()):
					# get the filename by starting a download and seeing if it is in the headers
					#	if not, then we default to the name of file in the url
					
					contentDispositionRegex = re.compile('^Content-Disposition:.*filename="?(?P<fileName>[^"]+)"?$', re.M)
					
					# this is a silly hack, but it is what I have. TODO: do this in python
					thisProcess = subprocess.Popen(["/usr/bin/curl", "-I", "-L", self.archiveLocation], stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True)
					(httpHeaders, myError) = thisProcess.communicate()
					
					if thisProcess.returncode != 0:
						# TODO: show some error here, we can't get the package name from the internet
						raise Exception('Unable to get the name of package: %s\n%s\n%s' % ( self.archiveLocation, httpHeaders, myError) ); # TODO: better errors

					contentDisposition = contentDispositionRegex.search(httpHeaders.split("HTTP/1")[-1])
					if contentDisposition:
						self.packageFileName = contentDispositionRegex.group('fileName')
					
					else:
						self.packageFileName = scannerResult.group('fileName')
										
				elif scannerResult.group("protocol") != None: # remember we have taken care of the "file://" case already
					# this isn't something we are supporting
					raise Exception(); # TODO: better errors
					
				else:
					# this should all be absolute-path files
					print "do more here"
		
		# we need to guess what the file type is based on the name
		
		fileExtension = self.fileLocationParser.search(self.packageFileName).group("extension").lower()
		if fileExtension == "dmg":
			self.packageType = "dmg"
			self.archiveType = "dmg"
		
		# see if we already have the package file in our cache
		#	if so, checksum it
		#		if correct setup and return
		
		if self.checkCacheForPackage():
			return
		
		# no local cached file, so if there is no archive location we have to bomb out
		if self.archiveLocation == None:
			self.setStatus("Invalid")
			raise Exception('Unable to find package: %s' % self.name) # TODO: better errors
			
		# since it is not in our cache, we need to retrieve it from the archive
		if self.retrieveFromArchive():
			return
			
		# since it is not in the cache, and we could not get it from the archive, we need to bomb out 
		raise Exception() # TODO: better errors
	
	def printPackageInformation(self):
		
		if re.search("cache", self.sourceMessage, re.I):
			archiveSection = ""
		else:
			archiveSection = "".join(["\n\tArchive:\n\t\tType:\t\t\t", str(self.archiveType), "\n\t\tLocation:\t\t", str(self.archiveLocation), "\n\t\tChecksum:\t\t", str(self.archiveChecksum), "\n\t\tChecksum Type:\t\t", str(self.archiveChecksumType), "\n\t\tChecksum Correct:\t", str(self.archiveChecksumCorrect)])
		
		print "File:\t", self.name, "\n\tStatus:\t\t\t\t", self.status, "\n\tSource:\t\t\t\t", self.sourceMessage, archiveSection, "\n\tPackage\n\t\tFile Name:\t\t", self.packageFileName, "\n\t\tType:\t\t\t", self.packageType, "\n\t\tLocation:\t\t", self.packageLocation, "\n\t\tChecksum:\t\t", self.packageChecksum, "\n\t\tChecksum Type:\t\t", self.packageChecksumType, "\n\t\tChecksum Correct:\t", self.packageChecksumCorrect, "\n\t\tCache Location:\t\t", self.packageCacheLocation
	
	
	def checksum(self, fileLocation = None, thisChecksum = None, checksumType = None, archiveOrPackage = "package"):
		"This handles checksumming a local file: either a folder version or a single file"
		
		if self.packageType == "dmg":
			archiveOrPackage = "archive"
		
		if ( archiveOrPackage == "archive" and self.archiveChecksumType == None ) or ( archiveOrPackage == "package" and self.packageChecksumType == None ):
			self.setPackageChecksumCorrect(True)
			return True
		
		# if this is called without options, then it defaults to the package values
		if fileLocation == None:
			fileLocation = self.cacheFolderName
		
		if thisChecksum == None:
			if archiveOrPackage == "archive":
				thisChecksum = self.archiveChecksum
			else:
				thisChecksum = self.packageChecksum
			
		if checksumType == None:
			if archiveOrPackage == "archive":
				checksumType = self.archiveChecksumType
			else:
				checksumType = self.packageChecksumType
		
		# we need to have all of these values, and fail without them
		
		if checksum == None:
			raise Exception() # TODO: better errors
		
		resultChecksum = checksum.checksum(fileLocation, checksumType)['checksum']
		result = (thisChecksum == resultChecksum)
		
		if archiveOrPackage == "package":
			self.setPackageChecksumCorrect(result)
		else:
			self.setArchiveChecksumCorrect(result)
				
		return result
		
	def setStatus(self, newStatus):
		# TODO: check newStatus
		self.status = newStatus
		
	def setPackageChecksumCorrect(self, newStatus):
		if newStatus != True and newStatus != False:
			raise Exception(); # TODO: better errors
		self.packageChecksumCorrect = newStatus
		
	def setPackageType(self, newType):
		if newType != "flatfilepkg" and newType != "folderpkg" and newType != "folder" and newType != "dmg":
			raise Exception(); # TODO: better errors
		self.packageType = newType
		
	def setArchiveChecksumCorrect(self, newStatus):
		if newStatus == True or newStatus == False:
			self.archiveChecksumCorrect = newStatus
			return
		raise Exception(); # TODO: better errors
	
	def setPackageCacheLocation(self, newLocation):
		if os.path.exists(newLocation):
			self.packageCacheLocation = newLocation
			return
		raise Exception(); # TODO: better errors
		
	def setSourceMessage(self, newMessage):
		self.sourceMessage = newMessage
	
	def checkCacheForPackage(self):
		"This goes through the cache and userSuppliedPKGFolder folders, looking for a package with the name of this package (and the correct checksum, if there is one). If it finds one, it will return true, otherwise false"
		
		global cacheFolder
		global userSuppliedPKGFolder
		
		print "Looking for %s in cache folder" % self.packageFileName
		
		for selectedFolder in (userSuppliedPKGFolder, cacheFolder): 
		
			for thisFileName in os.listdir(selectedFolder):
				if thisFileName == self.packageFileName or (thisFileName + "/") == self.packageFileName: # TODO: allow for multiple files to be named the same thing (-1 -2, etc)
				
					thisFilePath = os.path.join(selectedFolder, thisFileName)
										
					if self.checksum(os.path.abspath(thisFilePath)):
						if os.path.isdir(thisFilePath) and not( re.search("\.(m)?pkg$", thisFileName, re.I) ):
							# a folder that is not a pkg or mpkg
							#	the checksum was already correct, so we are probably safe,
							#	but we will be paranoid and make sure that there is a pkg or mpkg inside
							
							foundIt = False
							for innerFileName in os.listdir(thisFilePath):
								if re.search("\.(m)?pkg$", innerFileName, re.I):
									foundIt = True
									break
							if not(foundIt):
								continue
							
							self.packageCacheLocation = thisFilePath + "/" # this is just in case things ever get more complicated
							self.setStatus("Verified")
							self.setPackageType("folder")
							self.setSourceMessage("Found in Cache");
							
							print "Found %s in archive" % self.packageFileName
							return True
							
						elif re.search("\.(m)?pkg$", thisFileName, re.I):
							# a pkg or a mpkg by itself
							
							self.packageCacheLocation = thisFilePath # this is just in case things ever get more complicated
							self.setStatus("Verified")
							
							if os.path.isfile(thisFilePath):
								self.setPackageType("flatfilepkg") 
							elif os.path.isdir(thisFilePath):
								self.setPackageType("folderpkg") 
							else: # TODO: should probably support links
								raise Exception(); # TODO: better errors
							
							self.setSourceMessage("Found in Cache");
							
							print "Found %s in archive" % self.packageFileName
							return True
						
						elif re.search("\.dmg$", thisFileName, re.I):
							# since the checksum is correct on the file (not referring to the internal one) this is probably ok
							#	but being paranoid... we will have hdiutil cheksum it at well
							
							# check with hdiutil to see if it should have a checksum
							hdiutilProcess = subprocess.Popen(['/usr/bin/hdiutil', 'imageinfo', '-plist', thisFilePath] , stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True)
							if hdiutilProcess.wait() != 0:
								raise Exception("There is something internally wrong with package: %s.\nhdiutil returned this when trying to checksum it:\n%s" % ( thisFilePath, myError )); # TODO: better errors
							
							imageInfoString = hdiutilProcess.stdout.read()
							imageInfoNSData = Foundation.NSString.stringWithString_(imageInfoString).dataUsingEncoding_(Foundation.NSUTF8StringEncoding)
							imageInfo, format, error = Foundation.NSPropertyListSerialization.propertyListFromData_mutabilityOption_format_errorDescription_(imageInfoNSData, Foundation.NSPropertyListImmutable, None, None)
							if error:
								raise Exception("There is something internally wrong with package: %s.\nhdiutil returned this when trying to get the image info:\n%s" % ( tempFilePath, myError )); # TODO: better errors
							
							if "Checksum Value" in imageInfo and imageInfo["Checksum Value"] != "":
								thisProcess = subprocess.Popen(["/usr/bin/hdiutil", "verify", thisFilePath], stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True)
								(myResponce, myError) = thisProcess.communicate()
							
								if thisProcess.returncode != 0:
									raise Exception("There is something internally wrong with package: %s.\nhdiutil returned this when trying to checksum it:\n%s" % ( thisFileName, myError )); # TODO: better errors
								
							self.setPackageType("dmg")
							self.setStatus("Verified")
							self.packageCacheLocation = thisFilePath
							self.setSourceMessage("Found in Cache");
							return True
	
						else:
							# not something we can deal with
							raise Exception("Unable to process package named: %s" % thisFileName); # TODO: better errors
		
		# otherwise we will just continue on
		print "Did not find %s in archive" % self.packageFileName
		return False
		
	def retrieveFromArchive(self):
		"This will look for a file in the location listed in archiveLocation"
						
		if self.archiveLocation == None:
			raise Exception(); # TODO: better errors
		
		checksumResult = checksum.checksum(self.archiveLocation, self.archiveChecksumType, returnCopy=True)
		
		if self.archiveChecksum != checksumResult['checksum']:
			raise Exception('The checksum on %s did not match! File was: %s:%s should have been: %s:%s' % (self.name, checksumResult['checksumType'], checksumResult['checksum'], self.archiveChecksumType, self.archiveChecksum) ) # TODO: improve error handling
		
		tempFilePath = checksumResult["cacheLocation"]
		
		self.setArchiveChecksumCorrect(True)
		
		self.setStatus("Downloaded")
		self.setSourceMessage("Downloaded from Archive");
		
		# determine the type of file, and open it as appropriate
		# then checksum it, and move it to the cache folder
		
		# TODO: allow for dmg's inside a zip, or tgz
		
		# unfortunately "file" does not do a good job of figuring out dmg's, se we are going to have to trust the name
		
		if os.path.splitext(tempFilePath)[1].lower() == ".dmg": # we have already made sure that everything is lower case
			self.archiveType = "dmg"
			
			# TODO: re-integrate the package unloading for a 4 field type
			
			# help hdiutil by giving the temp file a .dmg ending
			
			# checksum the dmg file, and then let hdiutil internally checksum it
			if self.archiveChecksum: # if there is no checksum, just trust it
				if not(self.checksum(tempFilePath, archiveOrPackage = "archive")):
					raise Exception # TODO: improve error handling
			
			# check with hdiutil to see if it should have a checksum
			hdiutilProcess = subprocess.Popen(['/usr/bin/hdiutil', 'imageinfo', '-plist', tempFilePath] , stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True)
			if hdiutilProcess.wait() != 0:
				raise Exception("There is something internally wrong with package: %s.\nhdiutil returned this when trying to checksum it:\n%s" % ( tempFilePath, myError )); # TODO: better errors
			
			imageInfoString = hdiutilProcess.stdout.read()
			imageInfoNSData = Foundation.NSString.stringWithString_(imageInfoString).dataUsingEncoding_(Foundation.NSUTF8StringEncoding)
			imageInfo, format, error = Foundation.NSPropertyListSerialization.propertyListFromData_mutabilityOption_format_errorDescription_(imageInfoNSData, Foundation.NSPropertyListImmutable, None, None)
			if error:
				raise Exception("There is something internally wrong with package: %s.\nhdiutil returned this when trying to get the image info:\n%s" % ( tempFilePath, myError )); # TODO: better errors
			
			if "Checksum Value" in imageInfo and imageInfo["Checksum Value"] != "":
				thisProcess = subprocess.Popen(["/usr/bin/hdiutil", "verify", tempFilePath], stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True)
				(myResponce, myError) = thisProcess.communicate()
				
				if thisProcess.returncode != 0:
					raise Exception("There is something internally wrong with package: %s.\nhdiutil returned this when trying to checksum it:\n%s" % ( tempFilePath, myError )); # TODO: better errors
			
			# at this point we are as sure as we can be that this is the driod... er... dmg that we are looking for			
			targetLocation =  os.path.join(cacheFolder, self.packageFileName)
			shutil.copyfile(tempFilePath, targetLocation)
			
			# set flags on the file so that TimeMachine does not backup the file
			subprocess.call(["/usr/bin/xattr", "-w", "com.apple.metadata:com_apple_backup_excludeItem", "com.apple.backupd", targetLocation])
			
			self.setStatus("Verified")
			self.setPackageCacheLocation(targetLocation)
			return True
			
		elif os.path.splitext(tempFilePath)[1].lower() == ".pkg":
			self.archiveType = "flatfilepkg" # this should be a flat-file pkg
			
			# checksum the dmg file, and then let hdiutil internally checksum it
			if self.archiveChecksum: # if there is no checksum, just trust it
				if not(self.checksum(tempFilePath, archiveOrPackage = "archive")):
					raise Exception # TODO: improve error handling
			
			# move it to the appropriate spot
			targetLocation =  os.path.join(cacheFolder, self.packageFileName)
			shutil.copyfile(tempFilePath, targetLocation)
			
			subprocess.call(["/usr/bin/xattr", "-w", "com.apple.metadata:com_apple_backup_excludeItem", "com.apple.backupd", targetLocation])
			
			self.setStatus("Verified")
			self.setPackageCacheLocation(targetLocation)
			return True
			
		elif os.path.splitext(tempFilePath)[1].lower() == ".zip":
			# a pkg inside a zip file... this is a bit simplistic
			self.archiveType = "zip"			
			raise Exception # TODO: the ZIP mechanics
			
		else:
			# we don't know what type of file this is, so we bail
			raise Exception("Unknown file type: %s" % tempFilePath) # TODO: improve error handling
		
		if os.path.exists(tempFilePath):
			os.unlink(tempFilePath)

		return False
		
		
#--------------------------------MAIN--------------------------------

def main ():
	
	setup()
	
	global catalogFolder
	
	# ------- defaults -------
	processWithInstaDMG	= False
	outputVolumeName	= "MacintoshHD"
	outputFileName		= str(date.today().month) + "-" + str(date.today().day) + "-" + str(date.today().year)
	
	# ------- options -------
	try:
		options, filesToTry = getopt.gnu_getopt(sys.argv[1:], "hpv", ["help", "process", "version"])
	except getopt.GetoptError, err:
		print str(err) # TODO: cusomize the error message
		usage()
		sys.exit(2)
	
	for option, argument in options:
		if option in ("-h", "--help"):
			usage()
						
		elif option in ("-p", "--process"): # process with InstaDMG after a sucessfull result
			processWithInstaDMG = True
	
		elif option in ("-v", "--version"): 
			print "InstaUp2Date version %s" % versionString
			sys.exit(0)
			
	# --- police options ----
	
	# when there are options, they will be cleaned here
	
	# ------- process -------
	
	global cacheFolderName
	global customPKGFolder
		
	if len(filesToTry) < 1:
		raise Exception("No files were supplied!") # TODO: improve error handling
	
	thisController = instaUpToDate()
	
	for inputFilePath in filesToTry:	
		thisController.parseFile(inputFilePath, topLevel=True)
		
		if thisController.arrangeFolders() and processWithInstaDMG:
			# the run succeded, and it has been requested to run InstaDMG
			thisController.runInstaDMG()
		
		
#------------------------------END MAIN------------------------------

if __name__ == "__main__":
    main()
