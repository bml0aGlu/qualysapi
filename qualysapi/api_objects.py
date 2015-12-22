import datetime
import lxml
import logging
import pprint
import json
from multiprocessing import Process, Pool, Manager, get_context
from multiprocessing.queues import Queue
import queue
from qualysapi import exceptions


class CacheableQualysObject(object):
    '''
    A base class implementing the api framework
    '''
    def __init__(self, **kwargs):
        '''Superclass init function that handles json serializaiton'''
        if 'json' in kwargs:
            jsondict = json.loads(kwargs['json'])
            [setattr(self, key, jsondict[key]) for key in jsondict]


    def getKey(self):
        raise exceptions.QualysFrameworkException('You must implement this \
            function in your base class(es).')

    def __repr__(self):
        '''Represent y0'''
        return json.dumps(self.__dict__)

    def __eq__(self, other):
        '''Instance equality (simple dict key/value comparison'''
        return self.__dict__ == other.__dict__


class Host(CacheableQualysObject):
    def __init__(self, dns, id, ip, last_scan, netbios, os, tracking_method):
        self.dns = str(dns)
        self.id = int(id)
        self.ip = str(ip)
        last_scan = str(last_scan).replace('T', ' ').replace('Z', '').split(' ')
        date = last_scan[0].split('-')
        time = last_scan[1].split(':')
        self.last_scan = datetime.datetime(int(date[0]), int(date[1]), int(date[2]), int(time[0]), int(time[1]), int(time[2]))
        self.netbios = str(netbios)
        self.os = str(os)
        self.tracking_method = str(tracking_method)

class AssetGroup(CacheableQualysObject):
    def __init__(self, business_impact, id, last_update, scanips, scandns, scanner_appliances, title):
        self.business_impact = str(business_impact)
        self.id = int(id)
        self.last_update = str(last_update)
        self.scanips = scanips
        self.scandns = scandns
        self.scanner_appliances = scanner_appliances
        self.title = str(title)

    def addAsset(conn, ip):
        call = '/api/2.0/fo/asset/group/'
        parameters = {'action': 'edit', 'id': self.id, 'add_ips': ip}
        conn.request(call, parameters)
        self.scanips.append(ip)

    def setAssets(conn, ips):
        call = '/api/2.0/fo/asset/group/'
        parameters = {'action': 'edit', 'id': self.id, 'set_ips': ips}
        conn.request(call, parameters)

class ReportTemplate(CacheableQualysObject):
    def __init__(self, isGlobal, id, last_update, template_type, title, type, user):
        self.isGlobal = int(isGlobal)
        self.id = int(id)
        self.last_update = str(last_update).replace('T', ' ').replace('Z', '').split(' ')
        self.template_type = template_type
        self.title = title
        self.type = type
        self.user = user.LOGIN

class Report(CacheableQualysObject):
    '''
    An object wrapper around qualys report handles.

    Properties:

    NOTE: previously used ordered arguments are depricated.  Right now the
    class is backwards compatible, but you cannot mix and match.  You have to
    use the previous named order or keyword arguments, not both.

    expiration_datetime -- required expiration time of the report
    id -- required id of the report
    launch_datetime -- when the report was launched
    output_format -- the output format of the report
    size -- 
    status -- current qualys state of the report (scheduled, completed, paused,
    etc...)
    type -- report type
    user_login -- user who requested the report
    '''
    expiration_datetime = None
    id = None
    launch_datetime = None
    output_format = None
    size = None
    status = None
    type = None
    user_login = None
    def __init__(self, *args, **kwargs):
        # backwards-compatible ordered argument handling
        arg_order = [
            'expiration_datetime',
            'id',
            'launch_datetime',
            'output_format',
            'size',
            'status',
            'type',
            'user_login',
        ]
        # because of the old style handling where STATE is an etree element and
        # not a string the assumption must be handled before anyhting else...
        if len(args):
            [self.setattr(arg, args[n]) for (n,arg) in enumerate(n, arg_order)]
            # special handling for a single retarded attribute...
            if self.status is not None:
                self.status = status.STATE

        # set keyword values, prefer over ordered argument values if both get
        # supplied
        for key in arg_order:
            value = kwargs.pop(key, None)
            if value is not None:
                self.setattr(key, value)

        elem = kwargs.pop('elem', None)
        if elem is not None:
            # parse an etree element into string arguments
            self.status = status.STATE
            #TODO: implement
            pass

        json = kwargs.pop('json', None)
        if json is not None:
            # parse a json dict into arguments
            #TODO: implement
            pass

        # post attribute assignment processing
        self.expiration_datetime = str(self.expiration_datetime).replace('T', ' ').replace('Z', '').split(' ')
        self.launch_datetime = str(self.launch_datetime).replace('T', ' ').replace('Z', '').split(' ')
        # if id is a string change it to an int (used by other api objects)
        if isinstance(self.id, str):
            self.id = int(self.id)

    def download(self, conn):
        call = '/api/2.0/fo/report'
        parameters = {'action': 'fetch', 'id': self.id}
        if self.status == 'Finished':
            return conn.request(call, parameters)


class OptionProfile(CacheableQualysObject):
    title = None
    is_default = False
    def __init__(self, *args, **kwargs):
        el = None
        if len(args):
            el = args[0]
        elif kwargs.get('elem', None):
            el = kwargs.get('elem')
        if el is not None:
            self.title = el.text
            self.is_default = (el.get('option_profile_default', 1) == 0)


class Map(CacheableQualysObject):
    '''
    A simple object wrapper around the qualys api concept of a map.

    Params:
    name = None
    ref = None
    date = None
    domain = None
    status = None
    report_id = None
    '''
    name = None
    ref = None
    date = None
    domain = None
    status = None
    report_id = None

    def __init__(self, *args, **kwargs):
        '''Instantiate a new Map.'''

        #superclass handles json serialized properties
        super(Map, self).__init__(**kwargs)

        #instantiate from an etree element
        elem = kwargs.pop('elem', None)
        if elem is not None: #we are being initialized with an lxml element, assume it's in CVE export format
            logging.debug('Map with elem\n\t\t%s' % pprint.pformat(elem))
            self.ref = elem.get('ref', None)
            self.date = elem.get('date', None)
            self.domain = elem.get('domain', None)
            self.status = elem.get('status', None)

            for child in elem:
                if lxml.etree.QName(child.tag).localname.upper() == 'TITLE':
                    if child.text:
                        self.name = child.text
                    else:
                        self.name="".join(child.itertext())
                if lxml.etree.QName(child.tag).localname.upper() == \
                    'OPTION_PROFILE':
                    self.option_profiles = [OptionProfile(op) for op in child]

        # instance from kwargs
        for key in kwargs.keys():
            setattr(self, key, kwargs[key])

    def getKey(self):
        return self.ref if self.ref is not None else self.name

    def hasReport(self):
        return self.report_id is not None

    def setReport(self, **kwargs):
        report_id = kwargs.get('report_id', None)
        report = kwargs.get('report', None)
        if report_id is None and report is None:
            raise exceptions.QualysException('No report or report id.')
        self.report_id = report_id if report is None else report.id

    def __str__(self):
        '''Stringify this object.  NOT the same as repr().'''
        return '<Map name=\'%s\' date=\'%s\' ref=\'%s\' />' % (self.name, \
                self.date, self.ref)



class MapResult(Map):
    '''The actual results of a map.'''
    def __init__(self):
        '''A map result is a subclass of Map but it gets it's values of name,
        ref, date, domain, status from different fields in a result.'''
        raise QualysException('This class hasn\'t been implemented yet.')

    def __repr__(self):
        '''Represent y0'''
        raise QualysException('This class hasn\'t been implemented yet.')


class Scan(CacheableQualysObject):
    def __init__(self, assetgroups, duration, launch_datetime, option_profile, processed, ref, status, target, title, type, user_login):
        self.assetgroups = assetgroups
        self.duration = str(duration)
        launch_datetime = str(launch_datetime).replace('T', ' ').replace('Z', '').split(' ')
        date = launch_datetime[0].split('-')
        time = launch_datetime[1].split(':')
        self.launch_datetime = datetime.datetime(int(date[0]), int(date[1]), int(date[2]), int(time[0]), int(time[1]), int(time[2]))
        self.option_profile = str(option_profile)
        self.processed = int(processed)
        self.ref = str(ref)
        self.status = str(status.STATE)
        self.target = str(target).split(', ')
        self.title = str(title)
        self.type = str(type)
        self.user_login = str(user_login)

    def __repr__(self):
        ''' Represent this object in a human-readable string '''
        return '''
    Scan '%s':
        lanch datetime: %s
        option profile: %s
        scan ref: %s
        status: %s
        target: %s
        type: %s
        user: %s
        ''' % (self.title, self.launch_datetime, self.option_profile, self.ref,
                self.status, self.target, self.type, self.user_login)

    def cancel(self, conn):
        cancelled_statuses = ['Cancelled', 'Finished', 'Error']
        if any(self.status in s for s in cancelled_statuses):
            raise ValueError("Scan cannot be cancelled because its status is "+self.status)
        else:
            call = '/api/2.0/fo/scan/'
            parameters = {'action': 'cancel', 'scan_ref': self.ref}
            conn.request(call, parameters)

            parameters = {'action': 'list', 'scan_ref': self.ref, 'show_status': 1}
            self.status = lxml.objectify.fromstring(conn.request(call, parameters)).RESPONSE.SCAN_LIST.SCAN.STATUS.STATE

    def pause(self, conn):
        if self.status != "Running":
            raise ValueError("Scan cannot be paused because its status is "+self.status)
        else:
            call = '/api/2.0/fo/scan/'
            parameters = {'action': 'pause', 'scan_ref': self.ref}
            conn.request(call, parameters)

            parameters = {'action': 'list', 'scan_ref': self.ref, 'show_status': 1}
            self.status = lxml.objectify.fromstring(conn.request(call, parameters)).RESPONSE.SCAN_LIST.SCAN.STATUS.STATE

    def resume(self, conn):
        if self.status != "Paused":
            raise ValueError("Scan cannot be resumed because its status is "+self.status)
        else:
            call = '/api/2.0/fo/scan/'
            parameters = {'action': 'resume', 'scan_ref': self.ref}
            conn.request(call, parameters)

            parameters = {'action': 'list', 'scan_ref': self.ref, 'show_status': 1}
            self.status = lxml.objectify.fromstring(conn.request(call, parameters)).RESPONSE.SCAN_LIST.SCAN.STATUS.STATE


class BufferQueue(Queue):
    '''A thread/process safe queue for append/pop operations with the import
    buffer.  Initially this is just a wrapper around a collections deque but in
    the future it will be based off of multiprocess queue for access across
    processes (which isn't really possible right now)
    '''

    def __init__(self, **kwargs):
        super(BufferQueue,self).__init__(**kwargs)

    def consume(self, lim):
        '''Consume up to but no more than lim elements and return them in a new
        list, cleaning up the buffer.

        @params
        lim -- the maximum (limit) to consume from the list.  If less items
        exist in the list then that's fine too.
        '''
        lim = len(self) if len(self) < lim else lim
        return [self.popleft() for i in range(lim)]


class BufferStats(object):
    '''A simple wrapper for statistics about speeds and times.'''
    processed = 0

    #data processing stats
    updates = 0
    adds = 0
    deletes = 0

    #time stats
    start_time = None
    end_time = None


    def calculate_processing_average(self):
        '''Function to give the average time per operation between start_time,
        end_time and number processed.  Useful for metrics.'''
        pass

    def increment_updates(self):
        '''
        Increase updates..
        '''
        self.updates+=1

    def increment_insertions(self):
        '''
        Increase additions.
        '''
        self.adds+=1

    def decrement(self):
        '''
        Increase deleted items
        '''
        self.deletes+=1


class BufferConsumer(Process):
    '''This will eventually be a subclass of Process, but for now it is simply
    a consumer which will consume buffer objects and do something with them.
    '''
    bite_size = 1
    queue = None
    results_list = None
    def __init__(self, **kwargs):
        '''
        initialize this consumer with a bite_size to consume from the buffer.
        @Parms
        queue -- a BufferQueue object
        results_list -- Optional.  A list in which to store processing results.
        None by default.
        '''
        super(BufferConsumer, self).__init__() #pass to parent
        self.bite_size = kwargs.get('bite_size', 1000)
        self.queue = kwargs.get('queue', None)
        if self.queue is None:
            raise exceptions.ParsingBufferException('Consumer initialized without an input \
                queue.')

        self.results_list = kwargs.get('results_list', None)

    def run(self):
        '''a processes that consumes a queue in bite-sized chunks
        This class and method should be overridden by child implementations in
        order to actually do something useful with results.
        '''
        done = False
        while not done:
            try:
                item = self.queue.get(timeout=0.5)
                #the base class just logs this stuff
                if self.results_list is not None:
                    self.results_list.append(item)
            except queue.Empty:
                logging.debug('Queue timed out, assuming closed.')
                done = True


class ImportBuffer(object):
    '''
        This is a queue manager for a multiprocesses queue consumer for
        incoming data from qualys.  Rather than making huge lists of objects
        from xml, this buffer is used to place new objects as they are parsed
        out of the xml.  A trigger_limit and bite_size are set and used to
        trigger consumption of the queue.

        The general idea is that the buffer creates a single consumer on
        instantiation and tells it to start consuming queue items.  If the
        trigger_limit is reached then a second consumer is created which also
        begins consuming items from the que with each process consuming
        bite_size queue items at a time.  In this way concurrent processing of
        thread queues is retained.

        Consumers are responsible for making sure that transactionalized
        insertion of data doesn't clobber each other.  This module is not
        capable of ensuring that items inserted in one processes but not yet
        comitted to the database will be detected by another process.
        Obviously.
    '''
    queue = BufferQueue(ctx=get_context())
    stats = BufferStats()
    consumer = None

    trigger_limit = 5000
    bite_size = 1000
    max_consumers = 5

    results_list = None
    running = []


    def __init__(self, *args, **kwargs):
        '''
        Creates a new import buffer.

        @Params
        completion_callback -- Required.  A function that gets called when the buffer has
        been flushed and all consumers have finished.  Must allow keyword
        arguments list.
        consumer_callback -- Optional.  a function that gets called each time a consumer
        completes but the buffer hasn't been clearned or finished.
        trigger_limit -- set the consumer triggering limit.  The default is
        5000.
        bite_size -- set the consumer consumption size (bites NOT BYTES).  The
        default is 1000.
        max_consumers -- set the maximum number of queue consumers to spawn.
        The default is five.
        consumer -- the buffer consumer.  A type of multiprocessing.Process and
        responsible to do something with the results buffer.  This is optional,
        but not really useful in its optional form since it really just fills
        up a threadsafe list taken from the buffer.  By default this is set to
        a BufferConsumer(results_list=self.results_list).
        '''
        tlimit = kwargs.pop('trigger_limit', None)
        if tlimit is not None:
            self.trigger_limit = tlimit
        bsize = kwargs.pop('bite_size', None)
        if bsize is not None:
            self.bite_size = bsize
        mxcons = kwargs.pop('max_consumers', None)
        if mxcons is not None:
            self.max_consumers = mxcons

        self.manager = Manager()
        self.results_list = self.manager.list()

        self.consumer = kwargs.pop('consumer', None)
        if self.consumer is None:
            self.consumer = BufferConsumer


    def add(self, item):
        '''Place a new object into the buffer'''
        self.queue.put(item)
        #see if we should start a consumer...
        if not len(self.running):
            new_consumer = self.consumer(queue=self.queue, results_list=self.results_list)
            new_consumer.start()
            self.running.append(new_consumer)

        #check for finished consumers and clean them up...
        for csmr in self.running:
            if not csmr.is_alive():
                self.running.remove(csmr)


    def finish(self):
        '''Notifies the buffer that we are done filling it, forces it wait for
        processes to finish and then return the results, if any.'''
        for csmr in self.running:
            csmr.join()
        # turn this into a list instead of a managed list
        return list(self.results_list)


class MapReportRunner(Process):
    '''
    Grabs the first available queued report to run and attaches to it, starting
    the report running and then monitoring it periodically for the status until
    the report has finished.  If qualys returns with a concurrent scan/report
    limit, the process will sleep, periodically checking again to see if it can
    start the report.
    '''
    queue = None
    map_instance = None
    redis_cache = None
    def __init__(self, **kwargs):
        '''
        initialize this report runner.
        @Parms
        queue -- a standard multiprocessing.queue to generate reports on.
        redis_cache -- An instance of qcache.APICacheInstance This is the cache
        to use for updating the status of a map-report link (state reporting).
        '''
        super(BufferConsumer, self).__init__() #pass to parent
        self.queue = kwargs.get('queue', None)
        self.redis_cache = kwargs.get('redis_cache', None)
        if self.queue is None:
            raise ReportRunnerException('Runner initialized without an input \
                queue.')
        if self.redis_cache is None:
            raise ReportRunnerException('Runner initialized without a cache \
                instance in which to report on the status.')


    def run(self):
        '''Begin consuming map references and generating reports on them (also
        capable of resuming monitoring of running reports).
        '''
        done = False
        while not done:
            try:
                map_instance = self.queue.get(timeout=1)
                # see if the map we are working on has a report associated.
                while map_instance.report_id is None:
                    # check the cash to see if we are out of date...
                    rconn = self.redis_cache.getConnection()
                    rconn.load_api_object(obj=map_instance)
                    # recheck, and if still none then attempt to generate a
                    # report for the map_instance.
                    if map_instance.report_id is None:
                        pass


            except queue.Empty:
                logging.debug('Queue timed out, assuming closed.')
                done = True



obj_elem_map = {
    'MAP_REPORT' : Map,
    'MAP_RESULT' : MapResult,
}
