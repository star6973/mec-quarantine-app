import './Console.scss';
import { useState, useEffect } from "react";

function Console() {
    const [keyList, setKeyList] = useState();
    
    useEffect(() => {

    })

    return (
        <div className="password__ctrl">
            <div className="secure__top">
                <div className="robot__name">로봇</div>
                <div className="robot__tag">SeRo01</div>
                <div className="robot__service">방역안내</div>
            </div>
            <div className="secure__middle">
                <p>관리자 암호를 입력해주세요</p>
            </div>
            <div className="secure__bottom">
                <div className="secure__key__contianer">
                    <div className="secure__key">1</div>
                    <div className="secure__key">2</div>
                    <div className="secure__key">3</div>
                    <div className="secure__key secure__key__clear">CLR</div>
                </div>
                <div className="secure__key__contianer">
                    <div className="secure__key">4</div>
                    <div className="secure__key">5</div>
                    <div className="secure__key">6</div>
                    <div className="secure__key">0</div>
                </div>
                <div className="secure__key__contianer">
                    <div className="secure__key">7</div>
                    <div className="secure__key">8</div>
                    <div className="secure__key">9</div>
                    <div className="secure__key secure__key__enter">Enter</div>
                </div>                
            </div>

        </div>
    )
}

export default Console;