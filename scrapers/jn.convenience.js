/**
 * jn.convenience.js
 *
 * Some JavaScript extensions that make life easier for me.
 * Includes some Pythonic additions to prototypes as well
 * as formatting conveniences (right now just CSV).
 *
 * Formatting
 *
 *  - CSV Output
 * 		CSV Sanitization functions are added to the prototypes
 *      of Object, Array, String, and Number types. Array and Object
 *      have some irregularities that are addressed in the comments of
 * 		the relevant code. In general, though, any instance of these
 *		objects can be CSV-sanitized by calling [instance].csvSanitize().
 *		CSV sanitization ensures that an element is a String that is properly
 *		escaped and has the appropriate quotation marks around it, so that it
 *		can be added as a cell in a CSV file.
 *
 *		The method .toCSVEntry() is added to the Array.prototype so that
 *		an Array containing virtually any elements can be converted to
 *		a String that is suitable for printing into a CSV file. Types
 *		Object, Array, Boolean, String, Number, Null, and Undefined are
 *		all supported. See the comments to the relevant code for details.
 *
 *
 * Pythonic (and Python inspired) Extensions:
 *    - String
 *       + String.startsWith(needle)		Boolean
 *		 + String.endsWith(needle)			Boolean
 *		 + String.isNumeric()			    Boolean
 *		 + String.strip([chars])			String
 *		 + String.trim()					String (Note: usually already defined, alias of String.strip())
 *
 *	  - Array
 *		 + Array.contains(obj)				Boolean
 *
 * Copyright 2013 Joseph Nudell
 * Freely distributable under the MIT License.
 */		

var jn = jn || {};



// -- Pythonic Extensions -- //

// Add auxilliary functions to String prototype for convenience
if( typeof String.prototype.startsWith != 'function' ) {
    // Akin to Python .startswith()
    String.prototype.startsWith = function(str) {
        return this.slice(0, str.length) == str;
    };
}

if( typeof String.prototype.endsWith != 'function' ) {
	// Akin to Python str.endswith()
	String.prototype.endsWith = function(str) {
		return this.slice(str.length-1, str.length) == str;
	};
}


if( typeof String.prototype.isNumeric != 'function' ) {
    // tests numericity of contents
    String.prototype.isNumeric = function() {
        return !isNaN(parseFloat(this)) && isFinite(this);
    };
}


if( typeof String.prototype.strip != 'function' ) {
    // Akin to Python .strip() - This is a high-performance implementation.
    String.prototype.strip = function(needle) {
		if(needle!==undefined) {
			// Variation: trim specific substr (needle) from beginning and end
			return this.replace(RegExp("^"+needle+"+|"+needle+"+$", 'g'), '');
		}
		
		// Default: no needle is passed, trim ALL whitespace.
        var str = this.replace(/^\s+/, '');
        for( var i = str.length - 1; i >= 0; i-- ) {
            if( /\S/.test(str.charAt(i)) ) {
                str = str.substring(0, i+1);
                break;
            }
        }
        return str;
    };
}

if( typeof String.prototype.trim != 'function' ) {
	// Adds support for String.trim() if not available. Should be
	// Available in any modern JS environment, but just in case it isn't,
	// alias it to String.trim() (which with no argument will strip whitespace)
	String.prototype.trim = function() {
		return this.strip();
	};
}


if( typeof Array.prototype.contains != 'function' ) {
	Array.prototype.contains = function(obj) {
		// Tests for array membership in O(n).
		return (this.indexOf(obj)>-1);
	}
}


// -- Other useful extensions -- //

if( typeof String.prototype.csvSanitize != 'function' ) {
	// Create a valid (i.e. properly escaped and quoted) CSV cell from a string
	String.prototype.csvSanitize = function() {
		var str = this;
		var needsQuotes = false;
		if( str.search(/"/g) > -1 ) {
			str = str.replace(/"/g, '""');
			needsQuotes = true;
		}else if( str.search(/\n/) > -1 || str.search(/,/) > -1) {
			needsQuotes = true;
		}
		if(needsQuotes) {
			str = '"' + str + '"';
		}
		return str+"";
	};
}


if( typeof Number.prototype.csvSanitize != 'function' ) {
	// Create a valid CSV cell from a number
	Number.prototype.csvSanitize = function() {
		return Number.prototype.toString.call(this).csvSanitize();
	};
}


/* Temporarily disabled. Just use JSON.stringify(obj).csvSanitize, or deal with serializing objects yourself.
if( typeof Object.prototype.csvSanitize != 'function' ) {
	// Create a valid CSV cell from an object
	Object.prototype.csvSanitize = function(serializer) {
		// Have to convert this Object to a String. If serializer is
		// passed, use this function to convert Object to String. If not passed
		// Check if Object instance has defined a toString method for itself and use
		// that. Last resort is to use JSON.stringify. Note that Object.prototype.toString
		// is never used, since (unless overridden) it will only return "[object Object]",
		// which is entirely useless for our purposes. If you do happen to override
		// Object.prototype.toString, then pass Object.prototype.toString.call as the
		// serializer to use it.
		if(serializer!==undefined) {
			return serializer(this).csvSanitize();
		}
		if(this.hasOwnProperty('toString')) {
			return this.toString().csvSanitize();
		}
		return JSON.stringify(this).csvSanitize();
	};
}
*/


if( typeof Array.prototype.csvSanitize != 'function' ) {
	// Sanitize Array for CSV. The implementation is a little bit
	// strange. Each element inside the Array is converted to a String first,
	// using the stringifier parameter, or if this is not passed, by calling 
	// each elements native .toString() method. (Obviously an error will occur
	// if such a method does not exist.) The Array is then joined using the
	// delimiter specified (or a comma if none is specified). Finally, this
	// entire stringified Array is csvSanitize-d using the String.prototype.csvSanitize
	// method defined above.
	Array.prototype.csvSanitize = function(delimiter, stringifier) {
		// Array.prototyoe.csvSanitize([delim], [stringifier]);
		var defaultDelimiter = ",",
			defaultStringifier = function(obj) { return obj.toString(); };
		if(delimiter===undefined) delimiter = defaultDelimiter;
		if(!stringifier) stringifier = defaultStringifier;
		if(typeof delimiter=='function') {
			// Stringifier was passed as first argument
			delimiter = defaultDelimiter;
			stringifier = delimiter;
		}
		
		return Array.prototype.map.call(this, function(me) {
			return stringifier(me);
		}).join(delimiter).csvSanitize();
	};
}



if( typeof Array.prototype.toCSVEntry != 'function' ) {
	// Create a CSV entry from an Array. Optional emptyVals
	// parameter is a boolean indicating whether to display null
	// and undefined as blank cells (false, default); or as the
	// string values "null" and "undefined" respectively (true).
	Array.prototype.toCSVEntry = function(showEmptyVals) {
		if(showEmptyVals===undefined) showEmptyVals = false;
		var entry = "";
		
		for(var i=0; i<this.length; i++) {
			// Sanitize each element of `this` and add it to entry
			entry += entry.length? "," : "";
			var val = this[i];
			
			switch(typeof val) {
				case 'boolean':
					val = val.toString();
					break;
				case 'object':
					if(val===null) {
						val = showEmptyVals? 'null': "";
					}else{
						// sanitize serialized object
						val = JSON.stringify(val).csvSanitize();
					}
					break;
				case 'undefined':
					val = showEmptyVals? "undefined" : "";
					break;
				default:
					// csvSanitize should have been installed for every other
					// type above. If it wasn't, you're gonna have a bad time.
					val = val.csvSanitize();
			} // end of switch(typeof val)
			
			entry += val;
		} // End of for-loop through this elements
		
		return entry;
	}; // end of Array.prototype.toCSVEntry installer
}
	
	
	
	
	
	
	
// -- Easy selection (transparently switch from XPath to CSS) --
var $j = $j || {};
(function(_) {
	var queryLib = {
		//
		// Query extension for jn library
		//
		//
		// Detemrine type of query based on how it begins
		_typeOfQuery : function(q) {
			return (q.startsWith('./') || q.startsWith('/'))? "xpath" : "css";
		},
		//
		// 
		// Make selections
		//
		selectFirst : function(selector, type) {
			// Select the first element matching query. The type can
			// be automatically determined (just make sure you start XPath
			// queries with "./" or "/"), or it can be passed explicitly.
			if(type===undefined) type = _._typeOfQuery(selector);
			
			// Check type of query
			type = type.toLowerCase();
			if(!['xpath', 'css'].contains(type)) return null;
			
			if(type=='xpath') {
				// Perform an XPath query, return first element OR the
				// result of the query (might be a number or a string)
				var r= document.evaluate(selector,
										 document,
										 null,
										 XPathResult.FIRST_ORDERED_NODE_TYPE,
										 null).singleNodeValue;
				return r;
			}else if(type=='css') {
				// return document.querySelector(query)
				return document.querySelector(selector);
			}
		},
		//
		//
		// 
		// Select All nodes matching selector
		//
		selectAll : function(selector, type) {
			// Select all elements matching a query (ordered). Note that no matter
			// what query type is used, this method will return an Array of nodes. It
			// will NOT return a NodeList, even using CSS selectors!
			if(type===undefined) type = _._typeOfQuery(selector);
			
			// Check type of query
			type = type.toLowerCase();
			if(!['xpath', 'css'].contains(type)) return null;
			
			if(type=='xpath') {
				// XPath query (ordered)
				var nodes = document.evaluate(selector,
											  document,
											  null,
											  XPathResult.ORDERED_NODE_SNAPSHOT_TYPE,
											  null);
				return _._getNodeListFromXPathResult(nodes);
			}else if(type=='css') {
				var nodes = []
				Array.prototype.forEach.call(document.querySelectorAll(selector),
					function(me) {
						nodes.push(me);
					});
				return nodes
			}
		},
		//
		//
		//
		// Private function to generate an Array of nodes from an XPath iterator.
		//
		_getNodeListFromXPathResult : function(snapshots) {
			var nodes = [];
			for(var i=0; i<snapshots.snapshotLength; i++) {
				nodes.push(snapshots.snapshotItem(i));
			}
			return nodes;
		},
		//
		//
		//
		// Other queries.
		//
		query : function(query) {
			// perform non-selective xPath query. That is, an xPath query that
			// returns a primitive (number, string, boolean) instead of NodeSet.
			var xr = document.evaluate(query, document, null, XPathResult.ANY_TYPE, null);
			
			switch(xr.resultType) {
				case XPathResult.NUMBER_TYPE:
					return xr.numberValue;
					break;
				case XPathResult.STRING_TYPE:
					return xr.stringValue;
					break;
				case XPathResult.BOOLEAN_TYPE:
					return xr.booleanValue;
					break;
				default:
					// This means someone used .query for selection.
					// Failsafe for WebKit is to repeat query for Ordered Snapshot Node Set.
					return _.selectAll(query);
			}
		},
	//
	//
	//
	};
	
	// Install queryLib. Overwrites anything existing priorly in _.fn namespace!
	Object.keys(queryLib).forEach(function(key) {
		_[key] = queryLib[key];
	});
})($j, 'query');