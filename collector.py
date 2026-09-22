from sources.lever import get_lever_jobs
from sources.greenhouse import get_greenhouse_jobs
from sources.ashby import get_ashby_jobs
from sources.smartrecruiters import get_smartrecruiters_jobs
from sources.workday import get_workday_jobs
from sources.amazon import get_amazon_jobs
from sources.workable import get_workable_jobs


async def get_jobs():
    lever_jobs = await get_lever_jobs()
    greenhouse_jobs = await get_greenhouse_jobs()
    ashby_jobs = await get_ashby_jobs()
    smartrecruiters_jobs = await get_smartrecruiters_jobs()
    workday_jobs = await get_workday_jobs()
    #amazon_jobs = await get_amazon_jobs()
    workable_jobs = await get_workable_jobs()

    print("Workable:", len(workable_jobs))
    print("Lever:", len(lever_jobs))
    print("Greenhouse:", len(greenhouse_jobs))
    print("Ashby:", len(ashby_jobs))
    print("SmartRecruiters:", len(smartrecruiters_jobs))
    print("Workday:", len(workday_jobs))
    #print("Amazon:", len(amazon_jobs))

    return (
        lever_jobs
        + greenhouse_jobs
        + ashby_jobs
        + smartrecruiters_jobs
        + workday_jobs
        #+ amazon_jobs
        + workable_jobs
    )