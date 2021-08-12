import Lottie from "react-lottie";

export function LottieControl({loop, autoplay, data}) {
	return (
		<Lottie options={ {
			loop: loop,
			autoplay: autoplay,
			animationData: data,
			rendererSettings: {
				preserveAspectRatio: 'xMidYMid slice'
			}
		} } />
	)
}