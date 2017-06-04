import wx
import sys
import Model
import Utils
from FixCategories import FixCategories
import GanttChartPanel
from GetResults import GetResults, RidersCanSwap, RiderResult
from Undo import undo
import EditEntry

def UpdateSetNum( num ):
	if num is None:
		return
	from RiderDetail import ShowRiderDetailDialog
	mainWin = Utils.getMainWin()
	mainWin.setNumSelect( num )
	ShowRiderDetailDialog( mainWin, num )

def GetNowTime():
	race = Model.race
	return race.lastRaceTime() if race and race.isRunning() else None

class Gantt( wx.Panel ):
	def __init__( self, parent, id = wx.ID_ANY ):
		wx.Panel.__init__(self, parent, id)

		self.numSelect = None
		self.entry = None
		self.numBefore = None
		self.numAfter = None
		self.refreshTimer = None
		
		self.idCur = 0
		
		self.hbs = wx.BoxSizer(wx.HORIZONTAL)
		self.categoryLabel = wx.StaticText( self, label = _('Category:') )
		self.categoryChoice = wx.Choice( self )
		self.Bind( wx.EVT_CHOICE, self.doChooseCategory, self.categoryChoice )
		self.groupByStartWave = wx.CheckBox( self, label=_('Group by Start Wave') )
		self.Bind( wx.EVT_CHECKBOX, self.doGroupByStartWave, self.groupByStartWave )
		self.statsLabel = wx.StaticText( self )
		
		self.hbs.Add( self.categoryLabel, flag=wx.TOP | wx.BOTTOM | wx.LEFT | wx.ALIGN_CENTRE_VERTICAL, border=4 )
		self.hbs.Add( self.categoryChoice, flag=wx.ALL | wx.ALIGN_CENTRE_VERTICAL, border=4 )
		self.hbs.Add( self.groupByStartWave, flag=wx.ALL | wx.ALIGN_CENTRE_VERTICAL | wx.EXPAND, border=4 )
		self.hbs.Add( self.statsLabel, flag=wx.ALL | wx.ALIGN_CENTRE_VERTICAL | wx.EXPAND, border=4 )
		
		self.ganttChart = GanttChartPanel.GanttChartPanel( self )
		self.ganttChart.dClickCallback = UpdateSetNum
		self.ganttChart.rClickCallback = self.onRightClick
		#self.ganttChart.lClickCallback = self.onLeftClick
		self.ganttChart.getNowTimeCallback = GetNowTime

		bs = wx.BoxSizer(wx.VERTICAL)
		bs.Add(self.hbs, flag=wx.GROW|wx.HORIZONTAL)
		bs.Add(self.ganttChart, 1, wx.GROW|wx.ALL, 5)
		self.SetSizer(bs)
		bs.SetSizeHints(self)
		self.SetDoubleBuffered( True )

	def doChooseCategory( self, event ):
		Model.setCategoryChoice( self.categoryChoice.GetSelection(), 'ganttCategory' )
		self.refresh()
	
	def doGroupByStartWave( self, event ):
		if Model.race:
			Model.race.groupByStartWave = self.groupByStartWave.GetValue()
			wx.CallAfter( self.refresh )
		
	def reset( self ):
		self.ganttChart.numSelect = None

	def setNumSelect( self, num ):
		self.ganttChart.numSelect = num if num is None else '{}'.format(num)
	
	def onLeftClick( self, xPos, yPos, num, iRider, iLap, t ):
		if not Utils.mainWin:
			return
		Utils.mainWin.photoDialog.Show( True )
		Utils.mainWin.photoDialog.refresh( num, t )
	
	ids = []
	def NewId( self ):
		try:
			id = Gantt.ids[self.idCur]
		except IndexError:
			id = wx.NewId()
			Gantt.ids.append( id )
		self.idCur += 1
		return id
	
	def onRightClick( self, xPos, yPos, num, iRider, iLap ):
		with Model.LockRace() as race:
			if not race or num not in race.riders:
				return
			category = FixCategories( self.categoryChoice, getattr(race, 'ganttCategory', 0) )
			entries = race.getRider(num).interpolate()
			try:
				self.entry = entries[iLap]
				self.entryStart = entries[iLap-1]
				self.entryEnd = self.entry
			except (IndexError, KeyError):
				return
		self.setNumSelect( num )
		self.numSelect = num
		if Utils.isMainWin():
			wx.CallAfter( Utils.getMainWin().setNumSelect, self.ganttChart.numSelect )
			
		self.iLap = iLap
		self.iRow = iRider
		
		allCases = 0
		interpCase = 1
		nonInterpCase = 2
		if not hasattr(self, 'popupInfo'):
			self.popupInfo = [
				(self.NewId(), _('Add Missing Last Lap'),		_('Add Missing Last Lap'),		self.OnPopupAddMissingLastLap, allCases),
				(None, None, None, None, None),
				(self.NewId(), _('Pull after Lap End') + u'...',_('Pull after Lap End'),		self.OnPopupPull, allCases),
				(self.NewId(), _('DNF after Lap End') + u'...',	_('DNF after Lap End'),			self.OnPopupDNF, allCases),
				(None, None, None, None, None),
				(self.NewId(), _('Correct Lap End Time') + u'...',_('Change number or lap end time'),		self.OnPopupCorrect, interpCase),
				(self.NewId(), _('Shift Lap End Time') + u'...',_('Move lap end time earlier/later'),	self.OnPopupShift, interpCase),
				(self.NewId(), _('Delete Lap End Time') + u'...',_('Delete Lap End Time'),		self.OnPopupDelete, nonInterpCase),
				(None, None, None, None, None),
				(self.NewId(), _('Note') + u'...',				_('Add/Edit lap Note'),			self.OnPopupLapNote, allCases),
				(None, None, None, None, None),
				(self.NewId(), _('Turn off Autocorrect') + u'...',_('Turn off Autocorrect'),		self.OnPopupAutocorrect, allCases),
				(None, None, None, None, None),
				(self.NewId(), _('Swap with Rider before'),		_('Swap with Rider before'),	self.OnPopupSwapBefore, nonInterpCase),
				(self.NewId(), _('Swap with Rider after'),		_('Swap with Rider after'),		self.OnPopupSwapAfter, nonInterpCase),
				(None, None, None, None, None),
				(self.NewId(), _('Show Lap Details') + u'...', 	_('Show Lap Details'),			self.OnPopupLapDetail, allCases),
				(None, None, None, None, None),
				(self.NewId(), _('RiderDetail'),				_('Show RiderDetail Dialog'),	self.OnPopupRiderDetail, allCases),
				(self.NewId(), _('Results'), 					_('Switch to Results tab'),		self.OnPopupResults, allCases),
			]
			
			self.splitMenuInfo = [
					(self.NewId(),
					u'{} {}'.format(split-1, _('Split') if split-1 == 1 else _('Splits')),
					lambda evt, s = self, splits = split: s.doSplitLap(splits)) for split in xrange(2,8) ] + [
					(self.NewId(),
					_('Custom') + u'...',
					lambda evt, s = self: s.doCustomSplitLap())]
			for id, name, text, callback, cCase in self.popupInfo:
				if id:
					self.Bind( wx.EVT_MENU, callback, id=id )
			for id, name, callback in self.splitMenuInfo:
				self.Bind( wx.EVT_MENU, callback, id=id )
				
		caseCode = 1 if entries[iLap].interp else 2
		
		riderResults = dict( (r.num, r) for r in GetResults(category) )
		
		self.numBefore, self.numAfter = None, None
		for iRow, attr in [(self.iRow - 1, 'numBefore'), (self.iRow + 1, 'numAfter')]:
			if not(0 <= iRow < len(self.ganttChart.labels)):
				continue
			numAdjacent = GanttChartPanel.numFromLabel(self.ganttChart.labels[iRow])
			if RidersCanSwap( riderResults, num, numAdjacent ):
				setattr( self, attr, numAdjacent )
		
		menu = wx.Menu()
		for id, name, text, callback, cCase in self.popupInfo:
			if not id:
				Utils.addMissingSeparator( menu )
				continue
			if caseCode < cCase:
				continue
			if (name.endswith(_('before')) and not self.numBefore) or (name.endswith(_('after')) and not self.numAfter):
				continue
			menu.Append( id, name, text )
			
		if caseCode == 2:
			submenu = wx.Menu()
			for id, name, callback in self.splitMenuInfo:
				submenu.Append( id, name )
			Utils.addMissingSeparator( menu )
			menu.PrependSeparator()
			menu.PrependMenu( self.NewId(), _('Add Missing Split'), submenu )
			
		Utils.deleteTrailingSeparators( menu )
		try:
			self.PopupMenu( menu )
			menu.Destroy()
		except Exception as e:
			Utils.writeLog( 'Gantt:onRightClick: {}'.format(e) )

	def doSplitLap( self, splits ):
		with Model.LockRace() as race:
			try:
				num = int(self.ganttChart.numSelect)
				lap = self.iLap
				times = [e.t for e in race.riders[num].interpolate()]
			except (TypeError, KeyError, ValueError, IndexError):
				return
		EditEntry.AddLapSplits( num, lap, times, splits )
		
		wx.CallAfter( self.refresh )
		
	def doCustomSplitLap( self ):
		dlg = wx.NumberEntryDialog( self, message = "", caption = _("Add Missing Splits"), prompt = _("Missing Splits to Add:"),
									value = 1, min = 1, max = 500 )
		splits = None
		if dlg.ShowModal() == wx.ID_OK:
			splits = dlg.GetValue() + 1
		dlg.Destroy()
		if splits is not None:
			self.doSplitLap( splits )
		
	def swapEntries( self, num, numAdjacent ):
		if not num or not numAdjacent:
			return
		with Model.LockRace() as race:
			if (not race or
				num not in race or
				numAdjacent not in race.riders ):
				return
			e1 = race.getRider(num).interpolate()
			e2 = race.getRider(numAdjacent).interpolate()
			category = FixCategories( self.categoryChoice, getattr(race, 'ganttCategory', 0) )
			
		riderResults = dict( (r.num, r) for r in GetResults(category) )
		try:
			laps = riderResults[num].laps
			undo.pushState()
			with Model.LockRace() as race:
				EditEntry.SwapEntry( e1[laps], e2[laps] )
			wx.CallAfter( self.refresh )
		except KeyError:
			pass
	
	def OnPopupSwapBefore( self, event ):
		self.swapEntries( int(self.numSelect), self.numBefore )
		
	def OnPopupSwapAfter( self, event ):
		self.swapEntries( int(self.numSelect), self.numAfter )
	
	def OnPopupCorrect( self, event ):
		EditEntry.CorrectNumber( self, self.entry )
		
	def OnPopupShift( self, event ):
		EditEntry.ShiftNumber( self, self.entry )

	def OnPopupDelete( self, event ):
		EditEntry.DeleteEntry( self, self.entry )

	def OnPopupPull( self, event ):
		if not self.entry:
			return
		if not Utils.MessageOKCancel( self,
			u'{} {}: {} {}, {}?'.format(
				_('Bib'), self.entry.num,
				_('Pull Rider after lap'), self.entry.lap, Utils.formatTime(self.entry.t+1, True)),
			_('Pull Rider') ):
			return
		try:
			undo.pushState()
			with Model.LockRace() as race:
				if not race:
					return
				race.getRider(self.entry.num).setStatus( Model.Rider.Pulled, self.entry.t + 1 )
				race.setChanged()
		except Exception as e:
			pass
		wx.CallAfter( self.refresh )
		
	def OnPopupDNF( self, event ):
		if not self.entry:
			return
		if not Utils.MessageOKCancel( self,
			u'{} {}: {} {}, {}?'.format(
				_('Bib'), self.entry.num,
				_('DNF Rider after lap'), self.entry.lap, Utils.formatTime(self.entry.t+1, True)),
			_('DNF Rider') ):
			return
		try:
			undo.pushState()
			with Model.LockRace() as race:
				if not race:
					return
				race.getRider(self.entry.num).setStatus( Model.Rider.DNF, self.entry.t + 1 )
				race.setChanged()
		except:
			pass
		wx.CallAfter( self.refresh )
		
	def OnPopupAutocorrect( self, event ):
		if not self.entry:
			return
		if not Utils.MessageOKCancel( self,
			u'{} {}: {}?'.format(_('Bib'), self.entry.num, _('Turn off Autocorrect')),
			_('Turn off Autocorrect') ):
			return
		try:
			undo.pushState()
			with Model.LockRace() as race:
				if not race:
					return
				race.getRider(self.entry.num).setAutoCorrect( False )
				race.setChanged()
		except:
			pass
		wx.CallAfter( self.refresh )
	
	def OnPopupAddMissingLastLap( self, event ):
		if not self.entry:
			return
		num = self.entry.num
			
		race = Model.race
		if not race or num not in race.riders:
			return
			
		rider = race.riders[num]
			
		times = [t for t in rider.times]
		if len(times) < 2:
			return
			
		if rider.status != rider.Finisher:
			Utils.MessageOK( self, _('Cannot add Last Lap unless Rider is Finisher'), _('Cannot add Last Lap') )
			return
				
		undo.pushState()
		if rider.autocorrectLaps:
			if Utils.MessageOKCancel( self, _('Turn off Autocorrect first?'), _('Turn off Autocorrect') ):
				rider.autocorrectLaps = False
				
		waveCategory = race.getCategory( num )
		if waveCategory:
			times[0] = waveCategory.getStartOffsetSecs()
		tNewLast = times[-1] + times[-1] - times[-2]
				
		race.numTimeInfo.add( num, tNewLast )
		race.addTime( num, tNewLast )
		race.setChanged()
		
		wx.CallAfter( self.refresh )
	
	def OnPopupLapNote( self, event ):
		if not self.entry or not Model.race:
			return
		Model.race.lapNote = getattr(Model.race, 'lapNote', {})
		dlg = wx.TextEntryDialog( self, u"{} {}: {} {}: {}:".format(
						_('Bib'), self.entry.num, _('Lap'), self.entry.lap, _('Note'), 
					), _("Lap Note"),
					Model.race.lapNote.get( (self.entry.num, self.entry.lap), '' ) )
		ret = dlg.ShowModal()
		value = dlg.GetValue().strip()
		dlg.Destroy()
		if ret != wx.ID_OK:
			return
		undo.pushState()
		with Model.LockRace() as race:
			if value:
				race.lapNote[(self.entry.num, self.entry.lap)] = value
				race.setChanged()
			else:
				try:
					del race.lapNote[(self.entry.num, self.entry.lap)]
					race.setChanged()
				except KeyError:
					pass
		wx.CallAfter( self.refresh )
	
	def OnPopupLapDetail( self, event ):
		with Model.LockRace() as race:
			if not race:
				return
			tLapStart = self.entryStart.t
			tLapEnd = self.entryEnd.t
			
			iLap = self.entryStart.lap
			try:
				leaderNum = GanttChartPanel.numFromLabel( self.ganttChart.labels[0] )
				leaderEntries = race.getRider(leaderNum).interpolate()
				leaderEntryStart = leaderEntries[self.entryStart.lap]
				leaderEntryEnd = leaderEntries[self.entryEnd.lap]
			except:
				leaderEntryStart = None
				leaderEntryEnd = None
		
			try:
				riderInfo = race.excelLink.read()[self.entryEnd.num]
			except:
				riderInfo = {}
			
			try:
				riderName = u'{}, {} {}'.format(riderInfo['LastName'], riderInfo['FirstName'], self.entryEnd.num)
			except KeyError:
				try:
					riderName = u'{} {}'.format(riderInfo['LastName'], self.entryEnd.num)
				except KeyError:
					try:
						riderName = u'{} {}'.format(riderInfo['FirstName'], self.entryEnd.num)
					except KeyError:
						riderName = u'{}'.format(self.entryEnd.num)
						
			if leaderEntryStart:
				tDown = tLapStart - leaderEntryStart.t
				infoDownStart = u'\n' + u'{}: {} ({})'.format(
					_('Lap Start down from leader'), Utils.formatTime(tDown, True), leaderEntryStart.num)
			else:
				infoDownStart = ''
			if leaderEntryEnd:
				tDown = tLapEnd - leaderEntryEnd.t
				infoDownEnd = u'\n' + u'{}: {} {}'.format(
					_('Lap End down from leader'), Utils.formatTime(tDown, True), leaderEntryStart.num)
			else:
				infoDownEnd = ''
				
			infoStart = race.numTimeInfo.getInfoStr( self.entryStart.num, tLapStart )
			if infoStart:
				infoStart = u'\n{} {}'.format(_('Lap Start'), infoStart)
			infoEnd = race.numTimeInfo.getInfoStr( self.entryEnd.num, tLapEnd )
			if infoEnd:
				infoEnd = u'\n{} {}'.format(_('Lap End'), infoEnd)
		
			info = (u'{}: {}  {}: {}\n{}: {}   {}: {}\n{}: {}\n{}{}{}{}'.format(
					_('Rider'),		riderName,
					_('Lap'),		self.entryEnd.lap,
					_('Lap Start'),	Utils.formatTime(tLapStart),
					_('Lap End'),	Utils.formatTime(tLapEnd),
					_('Lap Time'),	Utils.formatTime(tLapEnd - tLapStart),
					infoDownStart, infoDownEnd, infoStart, infoEnd )).strip()
					
		Utils.MessageOK( self, info, _('Lap Details') )
		
	def OnPopupResults( self, event ):
		if Utils.isMainWin():
			Utils.getMainWin().showPageName( _('Results') )
			
	def OnPopupRiderDetail( self, event ):
		from RiderDetail import ShowRiderDetailDialog
		ShowRiderDetailDialog( self, self.numSelect )
		
	def OnPopupPhotos( self, event ):
		mainWin = Utils.mainWin
		if not mainWin:
			return
		mainWin.photoDialog.Show( True )
		mainWin.photoDialog.refresh( self.numSelect, self.entryEnd.t if self.entryEnd else None )
		
	def updateStats( self, results ):
		s = ''
		if results:
			total, projected, edited = 0, 0, 0
			getInfo = Model.race.numTimeInfo.getInfo if getattr(Model.race, 'numTimeInfo', None) else lambda num, t: False
			if Model.race.isRunning():
				tCur = Model.race.curRaceTime()
			else:
				tCur = 10.0*24.0*60.0*60.0
			for r in results:
				if not r.raceTimes:
					continue
				total		+= sum( 1 for t in r.raceTimes				if t < tCur ) - 1
				edited		+= sum( 1 for t in r.raceTimes				if t < tCur and getInfo(r.num, t) is not None )
				projected	+= sum( 1 for i, n in enumerate(r.interp)	if n and i < len(r.raceTimes) and r.raceTimes[i] < tCur )
			if total:
				toPercent = 100.0 / float(total)
				s = u'  {}: {}    {}: {} ({:.2f}%)    {}: {} ({:.2f}%)    {}: {} ({:.2f}%)    {}: {}'.format(
						_('Total Entries'),	total,
						_('Projected'),		projected,	projected * toPercent,
						_('Edited'),		edited,		edited * toPercent,
						_('Projected or Edited'), edited+projected, (edited+projected) * toPercent,
						_('Photos'),		getattr(Model.race, 'photoCount', 0) )
			
		self.statsLabel.SetLabel( s )
		self.hbs.Layout()
	
	def timerRefresh( self, doRefresh=True ):
		race = Model.race
		if self.IsShown() and race and race.isRunning():
			if doRefresh:
				wx.CallAfter( self.refresh )
			t = race.lastRaceTime()
			tNext = int(t + 5.0)
			tNext -= tNext % 5
			self.refreshTimer = wx.CallLater( max(1,int((tNext - t)*1000)), self.timerRefresh )
	
	def refresh( self ):
		if not Model.race:
			self.ganttChart.SetData( None )
			self.updateStats( None )
			return
		
		race = Model.race
		category = FixCategories( self.categoryChoice, getattr(race, 'ganttCategory', 0) )
		Finisher = Model.Rider.Finisher
		statusNames = Model.Rider.statusNames
		translate = _
		
		self.groupByStartWave.SetValue( race.groupByStartWave )
		self.groupByStartWave.Enable( not category )
		
		if race and race.isRunning():
			if self.refreshTimer:
				self.refreshTimer.Stop()
			self.timerRefresh( False )
		
		headerSet = set()
		if race.groupByStartWave and not category:
			results = []
			for c in sorted(race.getCategories(), key=lambda x:x.getStartOffsetSecs()):
				catResults = GetResults(c)
				if not catResults:
					continue
				# Create a name for the category as a bogus rider.
				rr = RiderResult( num='', status=Finisher, lastTime=None, raceCat=c, lapTimes=[], raceTimes=[], interp=[] )
				rr.FirstName = c.fullname
				headerSet.add( rr.FirstName )
				results.append( rr )
				results.extend( list(catResults) )
		else:
			results = GetResults( category )
		
		resultBest = (0, sys.float_info.max)
		labels, status = [], []
		for r in results:
			label = r.short_name(12)
			if r.num:
				label += u' {}'.format(r.num)
			labels.append( label )
			
			try:
				riderStatus = race.riders[r.num].status
				status.append( translate(statusNames[riderStatus] if riderStatus != Finisher else '') )
				if riderStatus == Finisher:
					resultBest = min( resultBest, (-r.laps, r.raceTimes[-1]) )
			except (IndexError, KeyError) as e:
				status.append( '' )

		data	= [r.raceTimes for r in results]
		interp	= [r.interp for r in results]
		try:
			nowTime = min( resultBest[1], Model.race.lastRaceTime() )
		except:
			nowTime = None
		self.ganttChart.SetData(data, labels, nowTime, interp,
								set(i for i, r in enumerate(results) if r.status != Finisher),
								Model.race.numTimeInfo,
								getattr( Model.race, 'lapNote', None),
								headerSet = headerSet,
								status = status,
		)
		self.updateStats( results )
	
	def commit( self ):
		wx.CallAfter( Utils.refreshForecastHistory )
	
if __name__ == '__main__':
	Utils.disable_stdout_buffering()
	app = wx.App(False)
	mainWin = wx.Frame(None,title="CrossMan", size=(600,400))
	Model.setRace( Model.Race() )
	Model.getRace()._populate()
	gantt = Gantt(mainWin)
	gantt.refresh()
	mainWin.Show()
	app.MainLoop()
