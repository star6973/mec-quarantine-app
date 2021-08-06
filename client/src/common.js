import './lottie.js'
import { Howl } from 'howler';

export function sound_and_speak(key, id, loop, cbcb) {
	let key_eng = key + '-eng.wav';
	let sound = createjs.Sound.play(id, {
		loop: (loop ? -1 : 0),
		volume: VOLUME_EFFECT
	})
	
	sound.on("complete", function() {
		inspection_speak_instance = new Howl({
			src: ['./contents/res/sound/speak/' + key_eng],
			autoplay: true,
			volume: 1.0,
			onend: function () {
				cbcb()
			}
		})
	})
}


export function create_quarantine_speak(key) {
	let key_eng = key + '.wav'
	let ret_obj = new Howl({
		src: ['./contents/res/sound/speak/' + key_eng],
		autoplay: true,
		volume: 1.0,
		loop: false
	});
}

export function lottieloader(target, item, loop, autoplay, anim) {
	lottie.destroy(target)

	var elem = document.getElementById(target);
	var animData = {
		container: elem,
		renderer: 'svg',
		loop: loop,
		autoplay: autoplay != null ? autoplay : true,
		rendererSettings: {
			progressiveLoad: true,
			preserveAspectRatio: 'xMidYMid slice',
		},
		path: item,
		name: target
	}
	anim = lottie.loadAnimation(animData)
	anim.setSubframe(false)

	return anim
}