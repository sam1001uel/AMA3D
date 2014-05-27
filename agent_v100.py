#TODO:

#-spawn (serailization), find resources
#-load method and execute (track)
#-check out os func kill -asdf 
#-die function
#-"db" has to be a global variable? or call open and close more often. (open whenever we need it?)
#-write to log file: concurrency
#-every function that deals with the db should check if connection db is opened if not, open it.
#-implement isOnly to check whether this is the only running agent (we want to sustain one agent at all time)
#---> or we might want to sustain a couple?


#Version 1.0.0
#Spawn linearly: After spawning, the parent agent picks up a task. 

#!/usr/bin/python
import MySQLdb
import subprocess # for running commands from command line
import pprint
import os.path
import traceback
import datetime
import time
import csv # for parsing csv files
import smtplib # for sending email messages
from email.mime.text import MIMEText

import AMA_globals as G # importing global variables

#connect to database with connectinfo
def connect_db(user, password, dbname):
	'''
	(str, int, str) -> int
	Given user information, try to connect database.
	Return 0 when success, if the first connection is not successful, try connect 5 times, if failed, return 1 and notify user. 
	Input arguments:
	user: your username
	password: your password
	dbname: the database we are going to log in
	'''
	try:
		file = open
		DB = G.DB
		DB = MySQLdb.connect(host=localhost, user, password, dbname)
		return 0
	except Exception, err:
		mins = 0
		while mins < 5:
			DB = MySQLdb.connect(host=localhost, user, password, dbname)
			time.sleep(60)
			mins+=1

		record_log_activity(str(err))
		notify_admin(str(err))

		# Rollback in case there is any error
		DB.rollback()
		return 1


def notify_admin(error):
	"""
	(str) -> ()
	Send an email including the error message to the admin(s).
	
	Keyword arguments:
	error -- the error message to be sent
	"""
	
	ADMINFILE = G.ADMINFILE
	MYEMAIL = G.MYEMAIL
	
	# assume admin info are stored in a file in the following format
	# Admin Name\tAdmin Email\tAdmin Cell \tOther Info\n
	msg = MIMEText(error);
	msg['Subject'] = "AMA3D - Error"
	msg['From'] = MYEMAIL	

	file = open(ADMINFILE, "r")
	parsed = csv.reader(file, delimiter="\t")
	listAdmin = list(parsed)
	count = 0

	for line in parsed:
		count+=1
		admin = listAdmin[count][1] 
		msg['To'] = admin
		msg = "Dear " + listAdmin[count][0] + ",\n" + msg + "\n" + "----AMA3D"
		# sending message through localhost
		s = smtplib.SMTP('localhost')
		s.sendmail(MYEMAIL, admin, msg.as_string())
		s.quit() 


def decide_next(seconds, threshold):
	"""
	(int, int) -> ()
	Decide what to do next (brain of the agent).
	
	Keyword arguments:
	time -- how long, in seconds, the agent will sleep when there is nothing to do
	threshold -- an integer defining "busy" (spawn if and only if the number of TC is greater than this integer)
	"""
	
	count = 0
	
	while not die():
		
		AGENT_ID = G.AGENT_ID
		DB = G.DB
		cursor = DB.cursor()
		
		#check for number of TC
		cursor.execute("""SELECT count(*) FROM TriggeringCondition WHERE Status = open""")
		results = cursor.fetchall
		if results[0][0] == 0: #no open TC => idle
			count += 1
			if count > 5 and not isOnly(): 
				#if idling more than five times and this is not the last agent: terminate
				terminate_self(False)
			else:
				time.sleep(seconds)
		else:
			if results[0][0] > threshold: #number of open TC greater than threshold => spawn one agent
				freeMachines = find_resources()
				spawn(freeMachines[0])
				
			#0 < number of TC < threshold => work (note: impossible to have negative number of TC)
		
			#pick the first open task 
			#Future implementation: can make agent smarter by choosing a task by type
			cursor.execute("""SELECT (id, idTaskResource, Parameters, IsLast) \
					FROM TriggeringCondition WHERE Status = open""")
			results = cursor.fetchall
			idTC = results[0][0]
			idTaskResource = results[0][1]
			IsLast = results[0][3]

			#globally stores parameters for to be used by load_methods
			#so that the agent can spawn more agents with preloaded methods
			#and just update PARAM
			PARAM = G.PARAM
			PARAM = results[0][2]
			
			#update TriggeringCondition table
			cursor.execute("""INSERT INTO TriggeringCondition(idAgent, Status) \
					VALUES (%d, 'in_progress') WHERE id = %d"""  %  (AGENT_ID, idTC))
			#update Agent table
			cursor.execute("""UPDATE Agent SET \
					StartTime = %s \
					Status = 'busy' \
					WHERE id = %d"""  %  (datetime.datetime.now(), AGENT_ID))

			#load and execute methods
			status = load_methods(idTaskResource)
			
			
			if status == 0:
				# successfully completed the task
				# remove TC and write to log file
				# addition of new TC will be taken care of by program executed
				cursor.execute("""DELETE FROM TriggeringCondition \
					WHERE id = %d"""  %  (idTC))
			
			else:
				# fail
				# reset TC 
					cursor.execute("""UPDATE TriggeringCondition SET \
					Status = 'open' \
					WHERE id = %d"""  %  (idTC))
					record_log_activity("Executing method failed: %d, error number: %d." % (idTC, status), G.MACHINE_ID)
				# if task failed, reset TC to open and log the errors
				# limit the number of times to attempt the TC?

	#if a die signal is present: self terminate
	terminate_self()


#spawn another agent: 
#create an agent by using this agent as template	
def spawn(machineID):
	"""
	(int, int) -> (int)
	Spawn a new agent on the machine represented by the given machineID.
	"""
	
	

#return a list of available machines by their machineID 
#in order of non-increasing availablity (most free first)
def find_resources():
	#changes: query for available machine by looking up the machine table
	#         update machine table??
	#return list of string or vector
	#ssh remotely, run a "top" command to check for CPU?
	#other ways to check without logging in?
	#look at how distributed machines work...?
	
#dynamically load the task-specific codes
def load_methods(idTR):
	""" 
	(int) -> (int)
	Dynamically load a module that its file path is known.
    
	Keyword arguments:
	idTR -- id number of TaskResource table
	"""
	DB = G.DB		
	cursor = DB.cursor()

	try:
   		# retrieve basepath where AMA3D is installed
   		base_path = cursor.execute("""SELECT Path FROM Machines WHERE\
		idMachine == %d""" % G.MACHINE_ID).fetchall()[0][0]
		
   		#retrive the relative path and the program in which the module has been written
   		stuff = cursor.execute("""SELECT Codepath, Program FROM TaskResource WHERE\
		idTaskResource == %d""" % idTR).fetchall()
		
		rel_path = stuff[0]["Codepath"]
		program = stuff[0]["Program"]
		
		code_path = base_path + "/" + rel_path
		
		# execute the program
		status = subprocess.call([program, code_path, G.PARAM], shell=True)
		
		return status
	
	except: 
		# db fails
		return 4444



def record_log_activity(activity, machineID):
	"""
	(str, int) -> ()
	Write activity summary of the agent to a 'LogTable' that is stored in the Database.
	This feature was added to handle the concurrency situation in which multiple agents 
	are writing to the log table at a time.
	
	Keyword arguments:
	str activity: contains the activity description to be added to log file. 
	              It could be an error message as well.
	int agentID: the unique agent identifier
	"""


	try:
		DB = G.DB
		cur = check_connection()         # returns DB cursor 
		timestamp = time.asctime()
		AGENT_ID = G.AGENT_ID

		# Insert and update LogTable in the database which has 4 attributes:
		# AgentId      MachineId    TimeStamp    Activity
		# -------      ---------    --------     --------
		# -------      ---------    --------     --------

		sql = """INSERT INTO LogTable(AgentId, MachineID, TimeStamp, Activity) \
		         VALUES ( %s, %s, %s, %s)"""  % (AGENT_ID, str(machineID), timestamp, str(activity))

		cur.execute(sql)
		DB.commit()
		return True

	except Exception as err:
		notify_admin(str(err))
		return False


#agent terminates itself
def terminate_self():
	'''
	() -> boolean
	Check if current agent has finish its job.
	If finished, delete the agent from status table and return true, otherwise return false.
	'''
	try:
		AGENT_ID = G.AGENT_ID
		DB = G.DB
		cursor = DB.cursor()
		sql1 = "SELECT Status FROM Agent WHERE AGENT_ID = %d"  %  AGENT_ID
		cursor.execute(sql1)
		status = cursors.fetchall()[0]

		if status == 0:
			sql2 = "DELETE FROM Agent WHERE AGENT_ID = %d"  %  AGENT_ID
			cursor.execute(sql2)
			return true
			

	except Exception as err:
		record_log_activity(str(err))
		return false 


def register():
	"""() -> boolean
        Register agent information to the database. Update global variable AGENT_ID
        from database. Return the completion status.

        : param:  none
        : effects: global AGENT_ID is set to autoincremented AGENT table id
        : returns: True for successful database insert, False otherwise.
        """

	rval = False

	DB = G.DB
	cursor = DB.cursor()

	registerTime = datetime.datetime.now()	
	
	sql = """INSERT INTO Agent \ 
		(RegisterTime, StartTime, Status, NumTaskDone) \
		VALUES (%s, 'not_yet_started', 1, 0)"""  %  (registerTime)
	try: 
		cursor.execute(sql)
		AGENT_ID = G.AGENT_ID
		AGENT_ID = DB.insert_id()
		DB.commit() #might not need this?
		rval = True
	except:
		DB.rollback()	
		rval = False
	
	return rval

#hibernate: do we need this? This is very similar to os's sleep command.
def hibernate():
	pass

#die
def die():
	"""
	()->()
	Listen for die signal and return true iff die signal is present.
	
	:param: none
	
	"""
	G.DIE = True

def check_connection():
	DB = G.DB
	return DB.cursor()
	

#acting as the main function
def essehozaibashsei():

	#configure some variables here? maybe better to pass in to main?
	time
	threshold
	# Setup a email account for agent.
	# Add a file in database for agent account.
	# Ask for the agent account file path.
	if connect_db(filepath): #TO-DO: add codes to open, read and parse file in connect_db or here?
		register()
		#check DIE here instead of in decide_next?
		#while !DIE
		decide_next(time, threshold)
	
	# Setup the email account, ask user for Adminfile location.
	# Add code for listen for die signal from user.

# agent.py's assumption/ preconditions	
# db set up. Including tables with the following info:
	# a list of available machines (uername + passwords + host + abs path 
	# of where the AMA3D folder is saved)
# files on machines (a AMA3D directory with agent.py... etc)
