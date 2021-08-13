import "./Inspection.css";
import * as Image from "./Image";
import { useState } from "react";
import { LottieControl } from "./Common";

const InspectUI = {
	moving: (
		<div className="inspection__move">
			<div className="inspection__title">Move To POI</div>
			<LottieControl loop={true} autoplay={true} data={Image.Moving} />
		</div>
	),
	default: (
		<div className="inspection__service__default">
			<div className="inspection__main__top">감시 중입니다.</div>
			<div className="inspection__main__bottom">
				<div className="inspection__main__bottom__left__default">
					<img src={ Image.TemperatureSmall } alt="default_temperature_img" />
					<img src={ Image.MaskSmall } alt="default_mask_img" />
					<img src={ Image.DistanceSmall } alt="default_distance_img" />
				</div>
				<div className="inspection__main__bottom__right">

				</div>
			</div>
		</div>
	),
	temperature: (
		<div className="inspection__service">
			<div className="inspection__main__top">발열 감시 중입니다.</div>
			<div className="inspection__main__bottom">
				<div className="inspection__main__bottom__left">
					<img src={ Image.TemperatureLarge } alt="temperature_img" />
				</div>
				<div className="inspection__main__bottom__right">

				</div>
			</div>
		</div>
	),
	mask: (
		<div className="inspection__service">
			<div className="inspection__main__top">마스크 감시 중입니다.</div>
			<div className="inspection__main__bottom">
				<div className="inspection__main__bottom__left">
					<img src={ Image.MaskLarge } alt="mask_img" />
				</div>
				<div className="inspection__main__bottom__right">

				</div>
			</div>
		</div>
	),
	distance: (
		<div className="inspection__service">
			<div className="inspection__main__top">거리두기 감시 중입니다.</div>
			<div className="inspection__main__bottom">
				<div className="inspection__main__bottom__left">
					<img src={ Image.DistanceLarge } alt="distance_img" />
				</div>
				<div className="inspection__main__bottom__right">

				</div>
			</div>
		</div>
	)
}

function Inspection ({ status }) {
	return (
        <div className="inspection__ctrl">
			{
				InspectUI[status]
			}
        </div>
    )
}

export default Inspection;