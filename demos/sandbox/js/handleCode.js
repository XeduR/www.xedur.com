function getCode() {
    var code = editor.getValue();
    return code;
}

function loadCode(target){
    if (typeof sampleProject === 'object' && typeof sampleProject[target] === 'object') {
        editor.setValue("");
        editor.clearHistory();
        editor.replaceRange( sampleProject[target].code, {line: 1} );
    }
}