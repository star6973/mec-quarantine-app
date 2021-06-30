"use strict";

let key_eng = "";

function create_quarantine_speak(key) {
	let key_eng = key + '.wav'
	let ret_obj = new Howl({
		src: ['./contents/res/sound/speak/' + key_eng],
		autoplay: true,
		volume: 1.0,
		loop: false
	});
}