

var possibleForms = ['form1', 'Form1', 'aspnetForm', 'frmMain'];

var theForm = null;
for(var i=0; i<possibleForms.length; i++) {
    if(!theForm) {
        theForm = document.forms[possibleForms[i]];
    }
}


$(theForm).append('<input type="hidden" name="__EVENTTARGET" id="__EVENTTARGET" value="" /><input type="hidden" name="__EVENTARGUMENT" id="__EVENTARGUMENT" value="" />');

function __doPostBack(eventTarget, eventArgument) {
    if (!theForm.onsubmit || (theForm.onsubmit() != false)) {
        theForm.__EVENTTARGET.value = eventTarget;
        theForm.__EVENTARGUMENT.value = eventArgument;
        theForm.submit();
    }
}