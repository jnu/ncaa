// Helpful functions for screenscraping.
// Requires jn.convenience.js convenience functions.

$ss = $ss || {};


$ss.getText = function (what) {
	var el = typeof what=='string'? $j.findFirst(what) : what;
	if(!el) return "Not Found";
	return el.innerText;
}


$ss.getValueByLabel = function (label, offset, cellType, exact) {
	// Locates the field label (of type cellType ... default is '*') that is offset
	// by given amount (default is 1). Set exact to match entire cell contents. You
	// can also set exact equal to a function that accepts one argument (label) and
	// create your own matching strategy. By default it uses exact matching.
	if(cellType===undefined) cellType = '*';
	if(offset===undefined) offset = 1;
	if(exact===undefined) exact = false;
	
	var matcher = '. = "'+label+'"';
	if(typeof exact=='function') {
		matcher = exact(label);
	}else if(exact===false){
		matcher = 'contains(., "'+label+'")';
	}
	
	var labelCell = $j.findFirst('.//'+cellType+'['+matcher+']');
	
	if(!labelCell) return "Not Found";
	
	var fieldValueCell = labelCell.nextElementSibling;
	for(var i=1; i<offset; i++) {
		if(!fieldValueCell) break;
		fieldValueCell = fieldValueCell.nextElementSibling;
		
	}
	
	if(!fieldValueCell) return "Not Found";
	
	return $ss.getText(fieldValueCell);
};