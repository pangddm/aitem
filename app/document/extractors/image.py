from app.llm.vision import analyze_image



def parse_image(path):


    result = analyze_image(

        path

    )


    return {


        "type":"image",


        "content":result,


        "source":path

    }