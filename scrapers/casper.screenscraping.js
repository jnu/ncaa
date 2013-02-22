/**
 * casper.screenscraping.js
 *
 * Convenient patches to CasperJS which expedite the
 * development of screenscrapers.
 *
 * To use, require this file in casper script.
 * E.g., require('./casper.screenscraping.js');
 *
 * Copyright 2013 Joseph Nudell
 * Freely distributable under the MIT License.
 */
 
casper.echo("Loading CasperJS ScreenScraping module ... ", 'COMMENT');
 
// Include some JS convenience functions both locally (for use in CasperJS
// and remotely (for access in remote page context via evaluate).
var jn = require('./jn.convenience.js'),
	$j = jn.$j;


 
casper.options.clientScripts = casper.options.clientScripts || [];
casper.options.clientScripts.push('jn.convenience.js');
 
// Include remote screenscraping utils 
casper.options.clientScripts.push('casper.screenscraping.remote.js');
casper.options.clientScripts.push('jquery.js');
casper.options.clientScripts.push('axdpatch.js');


// Common local casper configurations / optimizations

// A better CLI getter
casper.cli.getter = function(arg, def) {
	// Getter with default argument ... as it should be.
	if(def===undefined) def = null;
	return casper.cli.has(arg)? casper.cli.get(arg) : def;
}


// Fly under the radar ...
casper.userAgent('Mozilla/5.0 (Macintosh; Intel Mac OS X)');



casper.clickJS = function (selector) {
    // Perform a click on the given selector that only executes
    // whatever javascript action is given by the link. It does
    // NOT actually fire a click event! Also does not add any
    // Phantom navigation steps! This is useful for pages heavy
    // on AJAX.
    // Checks both onClick and href attributes, ONLY EXECUTES THE
    // LONGER JS CODE!
    // Returns true on success, false on failure.
    var r = casper.evaluate(function(selector) {
        try{
			var e = $j.selectFirst(selector);
			
			var clickMethod = "",
				hrefMethod = "";
			
			if(e.hasAttribute('onclick')) {
				clickMethod = e.getAttribute('onclick').replace(/javascript:/i, '');
			}
			
			if(e.hasAttribute('href')) {
				hrefMethod = e.href.replace(/javascript:/i, '');
			}
			
			var m1 = clickMethod===null? '' : clickMethod,
				m2 = hrefMethod===null? '' : hrefMethod;
			
			var toEval = m1.length>m2.length? m1: m2;
			
			// Set window.location if toEval is actually a URL (though this method should
			// not need to be invoked if the link in question actually points to a URL)
			toEval = toEval.substring(0,4)=='http'? 'window.location="'+toEval+'"' : toEval;
			
			
			if(toEval.length<1 || toEval.substring(0,1)=='#') {
				console.log("Nothing to evaluate ... triggering click event");
				jQuery(e).click();
			}else{
				console.log("Evaluating "+ toEval);
			}
			
			
				eval(toEval);
        }catch(error) {
            console.log(error.message);
        }

        return true;
    }, selector);
    return r!==null;
}




casper.today = function() {
	var currentTime = new Date(),
		month = currentTime.getMonth() + 1,
		day = currentTime.getDate(),
		year = currentTime.getFullYear();
	return year + "-" + month + "-" + day;
}