import "./Inspection.css";
import * as Image from "./Image";
import { useState } from "react";
import { LottieControl } from "./Common";

const InspectUI = {
	moving: (
		<div className="insp__mv">
			<div className="insp__title">Move To POI</div>
			<LottieControl loop={true} autoplay={true} data={Image.Moving} />
		</div>
	),
	default: (
		<div className="insp__sv__default">
			<div className="insp__main__top">감시 중입니다.</div>
			<div className="insp__main__bottom">
				<div className="insp__main__bottom__left__default">
					<img src={ Image.TemperatureSmall } alt="default_temperature_img" />
					<img src={ Image.MaskSmall } alt="default_mask_img" />
					<img src={ Image.DistanceSmall } alt="default_distance_img" />
				</div>
				<div className="insp__main__bottom__right">

				</div>
			</div>
		</div>
	),
	temperature: (
		<div className="insp__sv">
			<div className="insp__main__top">발열 감시 중입니다.</div>
			<div className="insp__main__bottom">
				<div className="insp__main__bottom__left">
					<img src={ Image.TemperatureLarge } alt="temperature_img" />
				</div>
				<div className="insp__main__bottom__right">

				</div>
			</div>
		</div>
	),
	mask: (
		<div className="insp__sv">
			<div className="insp__main__top">마스크 감시 중입니다.</div>
			<div className="insp__main__bottom">
				<div className="insp__main__bottom__left">
					<img src={ Image.MaskLarge } alt="mask_img" />
				</div>
				<div className="insp__main__bottom__right">

				</div>
			</div>
		</div>
	),
	distance: (
		<div className="insp__sv">
			<div className="insp__main__top">거리두기 감시 중입니다.</div>
			<div className="insp__main__bottom">
				<div className="insp__main__bottom__left">
					<img src={ Image.DistanceLarge } alt="distance_img" />
				</div>
				<div className="insp__main__bottom__right">

				</div>
			</div>
		</div>
	)
}

function Inspection ({ status }) {
	return (
        <div className="insp__ctrl">
			{
				InspectUI[status]
			}
        </div>
    )
}

export default Inspection;