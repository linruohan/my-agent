declare module "lunar-javascript" {
  export class Solar {
    static fromYmd(y: number, m: number, d: number): Solar;
    getLunar(): Lunar;
    getFestivals(): string[];
    getYear(): number;
    getMonth(): number;
    getDay(): number;
    getHour(): number;
    getMinute(): number;
  }

  export class Lunar {
    getJieQi(): string;
    getFestivals(): string[];
    getOtherFestivals(): string[];
    getDay(): number;
    getMonthInChinese(): string;
    getDayInChinese(): string;
    getYearShengXiao(): string;
    getYearInGanZhi(): string;
    getMonthInGanZhi(): string;
    getDayInGanZhi(): string;
    getDayYi(): string[];
    getDayJi(): string[];
    getPrevJieQi(): JieQi;
    getNextJieQi(): JieQi;
  }

  export class JieQi {
    getName(): string;
    getSolar(): Solar;
  }
}
