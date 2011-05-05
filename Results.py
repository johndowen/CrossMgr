import Model
import Utils
import wx
import wx.grid		as gridlib
import re
from string import Template
import ColGrid
from FixCategories import FixCategories, SetCategory

class Results( wx.Panel ):
	def __init__( self, parent, id = wx.ID_ANY ):
		wx.Panel.__init__(self, parent, id)
		
		self.showTimes = False
		self.showGaps = False
		self.showPositions = False
		self.showLapsCompleted = False
		
		self.rcInterp = set()
		self.numSelect = None
		self.isEmpty = True
		self.reSplit = re.compile( '[\[\]\+= ]+' )	# seperators for the fields.

		self.hbs = wx.BoxSizer(wx.HORIZONTAL)
		self.categoryLabel = wx.StaticText( self, wx.ID_ANY, 'Category:' )
		self.categoryChoice = wx.Choice( self )
		self.Bind(wx.EVT_CHOICE, self.doChooseCategory, self.categoryChoice)
		
		self.showTimesToggle = wx.ToggleButton( self, wx.ID_ANY, 'Show Times' )
		self.showTimesToggle.SetValue( self.showTimes )
		self.Bind( wx.EVT_TOGGLEBUTTON, self.onShowTimes, self.showTimesToggle )
		
		self.showGapsToggle = wx.ToggleButton( self, wx.ID_ANY, 'Show Gaps' )
		self.showGapsToggle.SetValue( self.showGaps )
		self.Bind( wx.EVT_TOGGLEBUTTON, self.onShowGaps, self.showGapsToggle )
		
		self.showLapsCompletedToggle = wx.ToggleButton( self,wx.ID_ANY, 'Show Laps Completed' )
		self.showLapsCompletedToggle.SetValue( self.showLapsCompleted )
		self.Bind( wx.EVT_TOGGLEBUTTON, self.onShowLapsCompleted, self.showLapsCompletedToggle )
		
		self.showPositionsToggle = wx.ToggleButton( self, wx.ID_ANY, 'Show Positions' )
		self.showPositionsToggle.SetValue( self.showPositions )
		self.Bind( wx.EVT_TOGGLEBUTTON, self.onShowPositions, self.showPositionsToggle )
		
		self.hbs.Add( self.categoryLabel, flag=wx.TOP | wx.BOTTOM | wx.LEFT | wx.ALIGN_CENTRE_VERTICAL, border=4 )
		self.hbs.Add( self.categoryChoice, flag=wx.ALL, border=4 )
		self.hbs.Add( self.showTimesToggle, flag=wx.ALL, border=4 )
		self.hbs.Add( self.showGapsToggle, flag=wx.ALL, border=4 )
		self.hbs.Add( self.showLapsCompletedToggle, flag=wx.ALL, border=4 )
		self.hbs.Add( self.showPositionsToggle, flag=wx.ALL, border=4 )

		self.whiteColour = wx.Colour( 255, 255, 255 )
		self.blackColour = wx.Colour( 0, 0, 0 )
		self.yellowColour = wx.Colour( 255, 255, 0 )
		self.greyColour = wx.Colour( 150, 150, 150 )
		
		self.grid = ColGrid.ColGrid( self )
		self.grid.SetRowLabelSize( 0 )
		self.grid.SetMargins( 0, 0 )
		self.grid.SetRightAlign( True )
		#self.grid.SetDoubleBuffered( True )
		self.grid.AutoSizeColumns( True )
		self.grid.DisableDragColSize()
		self.grid.DisableDragRowSize()
		
		self.Bind( wx.grid.EVT_GRID_SELECT_CELL, self.doNumSelect )
		self.Bind( wx.grid.EVT_GRID_CELL_LEFT_DCLICK, self.doNumDrilldown )
		self.Bind( wx.grid.EVT_GRID_CELL_RIGHT_CLICK, self.doRightClick )
		
		bs = wx.BoxSizer(wx.VERTICAL)
		#bs.Add(self.hbs)
		#bs.Add(self.grid, 1, wx.GROW|wx.ALL, 5)
		
		bs.Add(self.hbs, 0, wx.EXPAND )
		bs.Add(self.grid, 1, wx.EXPAND|wx.GROW|wx.ALL, 5 )
		
		self.SetSizer(bs)
		bs.SetSizeHints(self)
		
	def doRightClick( self, event ):
		self.doNumSelect( event )
		if self.numSelect is None:
			return
			
		if not hasattr(self, 'popupInfo'):
			self.popupInfo = [
				('Rider Detail',wx.NewId(), self.OnPopupRiderDetail),
				('History', 	wx.NewId(), self.OnPopupHistory),
			]
			for p in self.popupInfo:
				self.Bind( wx.EVT_MENU, p[2], id=p[1] )
		
		race = Model.getRace()
		
		menu = wx.Menu()
		for i, p in enumerate(self.popupInfo):
			if p[0] == 'Record' and not race.isRunning():
				continue
			menu.Append( p[1], p[0] )
		
		self.PopupMenu( menu )
		menu.Destroy()
		
	def OnPopupHistory( self, event ):
		if Utils.isMainWin():
			Utils.getMainWin().showPageName( 'History' )
	def OnPopupRiderDetail( self, event ):
		if Utils.isMainWin():
			Utils.getMainWin().showPageName( 'Rider Detail' )
		
	def onShowTimes( self, event ):
		self.showTimes = False if self.showTimes else True
		self.refresh()
		
	def onShowGaps( self, event ):
		self.showGaps = False if self.showGaps else True
		self.refresh()
		
	def onShowPositions( self, event ):
		self.showPositions = False if self.showPositions else True
		self.refresh()
		
	def onShowLapsCompleted( self, event ):
		self.showLapsCompleted = False if self.showLapsCompleted else True
		self.refresh()
		
	def showNumSelect( self ):
		race = Model.getRace()
		if race is None:
			return
			
		textColour = {}
		backgroundColour = {}
		for c in xrange(self.grid.GetNumberCols()):
			for r in xrange(self.grid.GetNumberRows()):
			
				value = self.grid.GetCellValue( r, c )
				if not value:
					break	
				
				cellNum = self.reSplit.split(value)[0]
				if cellNum == self.numSelect:
					textColour[ (r,c) ] = self.whiteColour
					backgroundColour[ (r,c) ] = self.blackColour if (r,c) not in self.rcInterp else self.greyColour
				else:
					rider = race[int(cellNum)]
					if rider.lapAdjust != 0:
						backgroundColour[ (r,c) ] = (0,220,220)
					elif (r, c) in self.rcInterp:
						backgroundColour[ (r,c) ] = self.yellowColour
					
		self.grid.Set( textColour = textColour, backgroundColour = backgroundColour )
		self.grid.Reset()
			
	def doNumDrilldown( self, event ):
		self.doNumSelect( event )
		if self.numSelect is not None and Utils.isMainWin():
			Utils.getMainWin().showPageName( 'History' )
	
	def doNumSelect( self, event ):
		if self.isEmpty:
			return
		row, col = event.GetRow(), event.GetCol()
		if row >= self.grid.GetNumberRows() or col >= self.grid.GetNumberCols():
			return
			
		value = self.grid.GetCellValue( row, col )
		numSelect = None
		if value:
			numSelect = self.reSplit.split(value)[0]
		if self.numSelect != numSelect:
			self.numSelect = numSelect
			self.showNumSelect()
		mainWin = Utils.getMainWin()
		if mainWin:
			historyCategoryChoice = mainWin.history.categoryChoice
			historyCatName = FixCategories( historyCategoryChoice )
			if historyCatName and historyCatName != 'All':
				catName = FixCategories( self.categoryChoice )
				if historyCatName != catName:
					if Model.race:
						Model.race.resultsCategory = self.categoryChoice.GetSelection()
					SetCategory( historyCategoryChoice, catName )
			mainWin.setNumSelect( numSelect )
				
	def doChooseCategory( self, event ):
		if Model.race:
			Model.race.resultsCategory = self.categoryChoice.GetSelection()
		self.refresh()
	
	def reset( self ):
		self.numSelect = None
	
	def setNumSelect( self, num ):
		self.numSelect = num if num is None else str(num)

	def clearGrid( self ):
		self.grid.Set( data = [], colnames = [], textColour = {}, backgroundColour = {} )
		self.grid.Reset()

	def refresh( self ):
		self.isEmpty = True
		self.rcInterp = set()	# Set of row/col coordinates of interpolated numbers.
		
		race = Model.getRace()
		if not race:
			self.clearGrid()
			return
		
		catName = FixCategories( self.categoryChoice, getattr(race, 'resultsCategory', 0) )
		self.hbs.Layout()
		
		colnames, results, dnf, dns, dq = race.getResults( catName )

		if not any([colnames, results, dnf, dns, dq]):
			self.clearGrid()
			return

		self.isEmpty = False

		# Format the results.
		data = []
		formatStr = '$num$otl'
		if self.showTimes:			formatStr += '=$t'
		if self.showGaps:			formatStr += '$gap'
		if self.showLapsCompleted:	formatStr += ' [$lap]'
		if self.showPositions:		formatStr += ' ($pos)'
		template = Template( formatStr )
		
		if results:
			leaderLap = results[0][0].lap
			leaderTime = results[0][0].t
			pos = 1
			for col, d in enumerate(results):
				data.append( [template.safe_substitute( dict(	num=e.num,
																otl=' OTL' if race[e.num].isPulled() else '',
																t=Utils.formatTime(e.t),
																gap='+%s' % Utils.formatTime(e.t - leaderTime) if e.lap == leaderLap else '',
																lap=e.lap,
																pos=row+pos) ) for row, e in enumerate(d)] )

				# self.rcInterp.update( (row, col) for row, e in enumerate(d) if e.interp )
				self.rcInterp.update( (row, col) for row, e in enumerate(d) if race[e.num].hasInterpolatedTime(e.t) )
				pos += len(d)
		
		if dnf:
			formatStr = '$num'
			if self.showTimes:			formatStr += '=$t'
			template = Template( formatStr )
			colnames.append( 'DNF' )
			data.append( [template.safe_substitute( dict(num=e[0], t=Utils.formatTime(e[1])) ) for j, e in enumerate(dnf)] )

		if dns:
			colnames.append( 'DNS' )
			data.append( [str(e[0]) for e in dns] )

		if dq:
			colnames.append( 'NP' )
			data.append( [str(e[0]) for e in dq] )

		self.grid.Set( data = data, colnames = colnames )
		self.grid.AutoSizeColumns( True )
		self.grid.Reset()

		self.showNumSelect()		

		self.grid.MakeCellVisible( 0, self.grid.GetNumberCols()-1 )
						
		# Fix the grid's scrollbars.
		self.grid.FitInside()

	def commit( self ):
		pass
		
if __name__ == '__main__':
	import cPickle as pickle
	app = wx.PySimpleApp()
	mainWin = wx.Frame(None,title="CrossMan", size=(600,200))
	Model.setRace( Model.Race() )
	Model.getRace()._populate()
	# Model.setRace( pickle.load(open(r'f:\Test Races\2009-09-16-test3-r15-.cmn', 'rb')) )
	# rider = Model.getRace()[217]
	# rider.lapAdjust = 3
	results = Results(mainWin)
	results.refresh()
	mainWin.Show()
	app.MainLoop()
